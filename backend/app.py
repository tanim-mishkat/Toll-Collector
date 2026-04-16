"""FastAPI app: toll events, vehicles, payments."""
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from config import (
    TOLL_RATES_BDT, DEFAULT_VEHICLE_CLASS,
    API_KEY, ALLOWED_ORIGINS, ENV,
)
from backend.db import init_db, get_session
from backend import models, schemas
from backend.notifications import send_notification, tpl_toll_notice
from backend.services import mark_event_paid, PaymentError, event_total_due
from backend.payments import router as payments_router
from backend import enforcement


# ---------- rate limiter ----------
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ---------- API key ----------
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def require_api_key(key: str = Security(_api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ---------- app ----------
app = FastAPI(
    title="Shohoj Toll — Prototype Backend",
    version="0.6.0",
    docs_url=None if ENV == "production" else "/docs",
    redoc_url=None if ENV == "production" else "/redoc",
    openapi_url=None if ENV == "production" else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(payments_router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    enforcement.start_background()


def _toll_for(vehicle_class: str) -> float:
    return float(TOLL_RATES_BDT.get(vehicle_class, TOLL_RATES_BDT["unknown"]))


def _get_or_create_vehicle(db: Session, plate: str) -> models.Vehicle:
    plate = plate.strip().upper()
    v = db.get(models.Vehicle, plate)
    if v is None:
        v = models.Vehicle(
            plate=plate,
            owner_name="UNKNOWN",
            vehicle_class=DEFAULT_VEHICLE_CLASS,
            registered=False,
        )
        db.add(v)
        db.flush()
    return v


def _vehicle_detail(db: Session, v: models.Vehicle) -> schemas.VehicleDetail:
    unpaid = db.scalars(
        select(models.TollEvent)
        .where(models.TollEvent.plate == v.plate,
               models.TollEvent.status != "PAID")
    ).all()
    recent = db.scalars(
        select(models.TollEvent)
        .where(models.TollEvent.plate == v.plate)
        .order_by(models.TollEvent.created_at.desc())
        .limit(10)
    ).all()
    total_due = sum(event_total_due(e) for e in unpaid)
    return schemas.VehicleDetail(
        plate=v.plate,
        owner_name=v.owner_name,
        phone=v.phone,
        vehicle_class=v.vehicle_class,
        balance_bdt=v.balance_bdt,
        brta_blocked=v.brta_blocked,
        registered=v.registered,
        total_due_bdt=total_due,
        unpaid_count=len(unpaid),
        recent_events=[schemas.TollEventOut.from_orm_with_total(e) for e in recent],
    )


@app.get("/health")
def health() -> dict:
    return {"ok": True, "time": datetime.utcnow().isoformat()}


@app.post("/toll-events", response_model=schemas.TollEventCreated,
          dependencies=[Depends(require_api_key)])
@limiter.limit("60/minute")
def create_toll_event(
    request: Request,
    payload: schemas.TollEventIn,
    db: Session = Depends(get_session),
):
    vehicle = _get_or_create_vehicle(db, payload.plate)
    amount = _toll_for(vehicle.vehicle_class)
    event = models.TollEvent(
        plate=vehicle.plate,
        gantry_id=payload.gantry_id,
        amount_bdt=amount,
        status="UNPAID",
        ocr_confidence=payload.ocr_confidence,
    )
    db.add(event)
    db.flush()
    db.refresh(event)

    body = tpl_toll_notice(vehicle, event)
    send_notification(
        db,
        to_phone=vehicle.phone,
        body=body,
        kind="TOLL_NOTICE",
        plate=vehicle.plate,
    )
    db.commit()
    db.refresh(event)
    db.refresh(vehicle)

    return schemas.TollEventCreated(
        event=schemas.TollEventOut.from_orm_with_total(event),
        vehicle=schemas.VehicleOut.model_validate(vehicle),
        message=body,
    )


@app.get("/vehicles/{plate}", response_model=schemas.VehicleDetail)
def get_vehicle(plate: str, db: Session = Depends(get_session)):
    v = db.get(models.Vehicle, plate.strip().upper())
    if v is None:
        raise HTTPException(404, "Vehicle not found")
    return _vehicle_detail(db, v)


@app.get("/vehicles", response_model=list[schemas.VehicleOut])
def list_vehicles(db: Session = Depends(get_session)):
    return db.scalars(select(models.Vehicle).order_by(models.Vehicle.plate)).all()


@app.get("/events", response_model=list[schemas.TollEventOut])
def list_events(
    limit: int = 50,
    status: str | None = None,
    db: Session = Depends(get_session),
):
    q = select(models.TollEvent).order_by(models.TollEvent.created_at.desc())
    if status:
        q = q.where(models.TollEvent.status == status.upper())
    return [schemas.TollEventOut.from_orm_with_total(e)
            for e in db.scalars(q.limit(limit)).all()]


@app.post("/events/{event_id}/pay", response_model=schemas.PayResponse)
def pay_event(event_id: int, db: Session = Depends(get_session)):
    try:
        event = mark_event_paid(db, event_id, channel="api")
    except PaymentError as e:
        code = 409 if "already" in str(e) else 404
        raise HTTPException(code, str(e))
    return schemas.PayResponse(
        event=schemas.TollEventOut.from_orm_with_total(event),
        message=f"Payment received for event #{event.id}. Dhonnobad.",
    )


@app.get("/sms", response_model=list[schemas.SmsOut])
def list_sms(
    limit: int = 50,
    phone: str | None = None,
    plate: str | None = None,
    db: Session = Depends(get_session),
):
    q = select(models.SmsMessage).order_by(models.SmsMessage.created_at.desc())
    if phone:
        q = q.where(models.SmsMessage.to_phone == phone)
    if plate:
        q = q.where(models.SmsMessage.plate == plate.strip().upper())
    return db.scalars(q.limit(limit)).all()


@app.get("/sms/{sms_id}", response_model=schemas.SmsOut)
def get_sms(sms_id: int, db: Session = Depends(get_session)):
    msg = db.get(models.SmsMessage, sms_id)
    if msg is None:
        raise HTTPException(404, "SMS not found")
    return msg


@app.get("/stats")
def stats(db: Session = Depends(get_session)) -> dict:
    total_events = db.scalar(select(func.count(models.TollEvent.id))) or 0

    def count_status(s: str) -> int:
        return db.scalar(
            select(func.count()).where(models.TollEvent.status == s)
        ) or 0

    total_col = (func.coalesce(func.sum(models.TollEvent.amount_bdt), 0.0)
                 + func.coalesce(func.sum(models.TollEvent.late_fee_bdt), 0.0)
                 + func.coalesce(func.sum(models.TollEvent.fine_bdt), 0.0))
    revenue = db.scalar(
        select(total_col).where(models.TollEvent.status == "PAID")
    ) or 0.0
    outstanding = db.scalar(
        select(total_col).where(models.TollEvent.status != "PAID")
    ) or 0.0
    blocked_vehicles = db.scalar(
        select(func.count()).where(models.Vehicle.brta_blocked == True)
    ) or 0

    return {
        "total_events": total_events,
        "by_status": {s: count_status(s) for s in
                      ("UNPAID", "REMINDED", "LATE", "FINED", "BLOCKED", "PAID")},
        "revenue_bdt": round(float(revenue), 2),
        "outstanding_bdt": round(float(outstanding), 2),
        "blocked_vehicles": blocked_vehicles,
    }


@app.post("/admin/tick")
def admin_tick() -> dict:
    """Run one enforcement cycle immediately. Handy for live demos to
    'fast-forward' time without waiting for the background tick."""
    counts = enforcement.run_cycle()
    return {"ok": True, "transitions": counts,
            "ran_at": datetime.utcnow().isoformat()}


@app.post("/admin/seed", dependencies=[Depends(require_api_key)])
def admin_seed(db: Session = Depends(get_session)) -> dict:
    """Seed demo vehicles into the DB. Requires API key."""
    from seed import FAKE_VEHICLES
    added = 0
    for plate, owner, phone, nid, vclass, bal, blocked in FAKE_VEHICLES:
        plate = plate.strip().upper()
        if db.get(models.Vehicle, plate):
            continue
        db.add(models.Vehicle(
            plate=plate, owner_name=owner, phone=phone, nid=nid,
            vehicle_class=vclass, balance_bdt=bal,
            brta_blocked=blocked, registered=True,
        ))
        added += 1
    db.commit()
    total = db.scalar(select(func.count(models.Vehicle.plate))) or 0
    return {"ok": True, "added": added, "total_vehicles": total}
