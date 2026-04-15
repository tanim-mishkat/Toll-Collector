"""HTML-based mock payment flows: bKash-style, Nagad-style, USSD simulator.

Real integration would replace these with merchant-API redirects (bKash
Tokenized Checkout, Nagad Merchant API, SSLCommerz, etc.). For the demo,
the same PIN form runs through a local state machine and ends by calling
the shared `mark_event_paid()` service.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend import models
from backend.db import get_session
from backend.services import mark_event_paid, PaymentError, event_total_due


TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


GATEWAYS = {
    "bkash": {
        "name": "bKash",
        "primary": "#e2136e",
        "short_code": "16247",
        "tagline": "Mobile Money",
    },
    "nagad": {
        "name": "Nagad",
        "primary": "#ec1c24",
        "short_code": "16167",
        "tagline": "Digital Financial Service",
    },
}


def _load_event(db: Session, event_id: int) -> models.TollEvent:
    event = db.get(models.TollEvent, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    return event


# ---------- landing page ----------

@router.get("/pay/{event_id}", response_class=HTMLResponse)
def pay_landing(event_id: int, request: Request,
                db: Session = Depends(get_session)):
    event = _load_event(db, event_id)
    vehicle = db.get(models.Vehicle, event.plate)
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "event": event,
        "vehicle": vehicle,
        "gateways": GATEWAYS,
    })


# ---------- bKash / Nagad mock flow ----------

@router.get("/pay/{event_id}/{gateway}", response_class=HTMLResponse)
def gateway_pin(event_id: int, gateway: str, request: Request,
                db: Session = Depends(get_session)):
    if gateway not in GATEWAYS:
        raise HTTPException(404, "Unknown gateway")
    event = _load_event(db, event_id)
    if event.status == "PAID":
        return RedirectResponse(f"/pay/{event_id}", status_code=303)
    vehicle = db.get(models.Vehicle, event.plate)
    return templates.TemplateResponse("gateway_pin.html", {
        "request": request,
        "event": event,
        "vehicle": vehicle,
        "gateway": GATEWAYS[gateway],
        "gateway_key": gateway,
        "error": None,
    })


@router.post("/pay/{event_id}/{gateway}", response_class=HTMLResponse)
def gateway_submit(event_id: int, gateway: str, request: Request,
                   pin: str = Form(...),
                   db: Session = Depends(get_session)):
    if gateway not in GATEWAYS:
        raise HTTPException(404, "Unknown gateway")
    event = _load_event(db, event_id)
    vehicle = db.get(models.Vehicle, event.plate)

    # Demo rule: accept any 4–5 digit numeric PIN.
    if not (pin.isdigit() and 4 <= len(pin) <= 5):
        return templates.TemplateResponse("gateway_pin.html", {
            "request": request,
            "event": event,
            "vehicle": vehicle,
            "gateway": GATEWAYS[gateway],
            "gateway_key": gateway,
            "error": "Invalid PIN. Enter 4 or 5 digits.",
        }, status_code=400)

    try:
        event = mark_event_paid(db, event_id, channel=gateway)
    except PaymentError as e:
        return templates.TemplateResponse("gateway_pin.html", {
            "request": request,
            "event": event,
            "vehicle": vehicle,
            "gateway": GATEWAYS[gateway],
            "gateway_key": gateway,
            "error": str(e),
        }, status_code=409)

    trx_id = f"{gateway.upper()[:3]}{event.id:08d}"
    return templates.TemplateResponse("gateway_success.html", {
        "request": request,
        "event": event,
        "vehicle": vehicle,
        "gateway": GATEWAYS[gateway],
        "trx_id": trx_id,
    })


# ---------- USSD simulator ----------
#
# Stateless: every step posts a `state` field naming the next screen,
# plus any prior inputs, all in hidden form fields. That keeps the demo
# trivial to follow — no sessions, no cookies, no backend state.

@router.get("/ussd", response_class=HTMLResponse)
def ussd_start(request: Request):
    return templates.TemplateResponse("ussd.html", {
        "request": request,
        "screen": "dial",
        "display": "Dial *999# to reach Shohoj Toll service.",
        "input_label": "",
        "next_state": "menu",
        "hidden": {},
        "options": [],
    })


@router.post("/ussd", response_class=HTMLResponse)
async def ussd_step(request: Request,
                    db: Session = Depends(get_session)):
    form = await request.form()
    state = form.get("state", "menu")
    plate = (form.get("plate") or "").strip().upper()
    event_id_raw = form.get("event_id", "")
    choice = (form.get("choice") or "").strip()
    pin = (form.get("pin") or "").strip()

    ctx = {
        "request": request,
        "hidden": {},
        "options": [],
        "input_label": "",
        "next_state": "menu",
    }

    if state == "menu":
        ctx.update({
            "screen": "menu",
            "display": "ShohojToll\n1. Check dues\n2. Pay toll\n0. Exit",
            "input_label": "Reply:",
            "next_state": "menu_choice",
        })
        return templates.TemplateResponse("ussd.html", ctx)

    if state == "menu_choice":
        if choice == "0":
            ctx.update({"screen": "end",
                        "display": "Session ended.",
                        "next_state": "menu"})
        elif choice in ("1", "2"):
            ctx.update({
                "screen": "plate",
                "display": "Enter vehicle plate:",
                "input_label": "Plate:",
                "next_state": "plate_entered",
                "hidden": {"intent": "check" if choice == "1" else "pay"},
            })
        else:
            ctx.update({"screen": "menu",
                        "display": "Invalid reply. 1, 2 or 0.",
                        "input_label": "Reply:",
                        "next_state": "menu_choice"})
        return templates.TemplateResponse("ussd.html", ctx)

    if state == "plate_entered":
        intent = form.get("intent", "check")
        vehicle = db.get(models.Vehicle, plate) if plate else None
        if vehicle is None:
            ctx.update({
                "screen": "plate",
                "display": f"No record for '{plate}'. Try again.",
                "input_label": "Plate:",
                "next_state": "plate_entered",
                "hidden": {"intent": intent},
            })
            return templates.TemplateResponse("ussd.html", ctx)

        from sqlalchemy import select
        unpaid = db.scalars(
            select(models.TollEvent)
            .where(models.TollEvent.plate == plate,
                   models.TollEvent.status != "PAID")
            .order_by(models.TollEvent.created_at.asc())
        ).all()

        if not unpaid:
            ctx.update({
                "screen": "end",
                "display": f"{plate}\nNo dues. Thank you.",
                "next_state": "menu",
            })
            return templates.TemplateResponse("ussd.html", ctx)

        if intent == "check":
            block_tag = " [BRTA BLOCK]" if vehicle.brta_blocked else ""
            lines = [f"{plate}{block_tag}", f"{len(unpaid)} unpaid"]
            for e in unpaid[:3]:
                lines.append(f"#{e.id} BDT {event_total_due(e):.0f} {e.status}")
            ctx.update({
                "screen": "end",
                "display": "\n".join(lines),
                "next_state": "menu",
            })
            return templates.TemplateResponse("ussd.html", ctx)

        # intent == "pay" — show oldest unpaid, ask for PIN
        e = unpaid[0]
        ctx.update({
            "screen": "pin",
            "display": (f"Pay BDT {event_total_due(e):.0f}\n"
                        f"Ref #{e.id} {plate}\nStatus: {e.status}\n"
                        f"Enter bKash PIN:"),
            "input_label": "PIN:",
            "next_state": "pin_entered",
            "hidden": {"event_id": str(e.id), "plate": plate},
        })
        return templates.TemplateResponse("ussd.html", ctx)

    if state == "pin_entered":
        if not event_id_raw.isdigit():
            ctx.update({"screen": "end",
                        "display": "Session error. Dial again.",
                        "next_state": "menu"})
            return templates.TemplateResponse("ussd.html", ctx)
        if not (pin.isdigit() and 4 <= len(pin) <= 5):
            ctx.update({
                "screen": "pin",
                "display": "Wrong PIN format. 4 or 5 digits.",
                "input_label": "PIN:",
                "next_state": "pin_entered",
                "hidden": {"event_id": event_id_raw, "plate": plate},
            })
            return templates.TemplateResponse("ussd.html", ctx)

        try:
            event = mark_event_paid(db, int(event_id_raw), channel="ussd")
        except PaymentError as pe:
            ctx.update({"screen": "end",
                        "display": f"Failed: {pe}",
                        "next_state": "menu"})
            return templates.TemplateResponse("ussd.html", ctx)

        ctx.update({
            "screen": "end",
            "display": (f"Paid BDT {event_total_due(event):.0f}\n"
                        f"Ref #{event.id}\nDhonnobad."),
            "next_state": "menu",
        })
        return templates.TemplateResponse("ussd.html", ctx)

    # unknown state → reset
    ctx.update({"screen": "dial",
                "display": "Dial *999#.",
                "next_state": "menu"})
    return templates.TemplateResponse("ussd.html", ctx)
