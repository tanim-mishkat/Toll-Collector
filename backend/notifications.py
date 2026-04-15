"""Outbound notifications (mocked SMS + optional Telegram mirror).

Real BD rollout would plug a telco SMS gateway here (GP / Robi / Banglalink).
For the prototype, every message is persisted to the `sms_messages` table so
the dashboard can render a phone-screen panel, and optionally mirrored to a
single Telegram chat for a live on-phone demo effect.
"""
from __future__ import annotations

import threading
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    SMS_SENDER_NAME, TOLL_HELPLINE, PAY_DEADLINE_DAYS,
    BACKEND_URL,
)
from backend import models


# ---------- templates ----------

def tpl_toll_notice(vehicle: models.Vehicle,
                    event: models.TollEvent) -> str:
    when = event.created_at.strftime("%d-%b %H:%M")
    pay_link = f"{BACKEND_URL}/pay/{event.id}"
    return (
        f"[{SMS_SENDER_NAME}] Vehicle {vehicle.plate} passed "
        f"{event.gantry_id} on {when}. Toll: BDT {event.amount_bdt:.0f}. "
        f"Pay: {pay_link}  or dial *999#. "
        f"Due in {PAY_DEADLINE_DAYS} days. Ref #{event.id}. "
        f"Helpline: {TOLL_HELPLINE}."
    )


def _total_due(event: models.TollEvent) -> float:
    return (event.amount_bdt or 0.0) + (event.late_fee_bdt or 0.0) + (event.fine_bdt or 0.0)


def tpl_payment_confirmation(vehicle: models.Vehicle,
                             event: models.TollEvent) -> str:
    return (
        f"[{SMS_SENDER_NAME}] Payment received: BDT {_total_due(event):.0f} "
        f"for {vehicle.plate} (Ref #{event.id}). Dhonnobad."
    )


def tpl_reminder(vehicle: models.Vehicle,
                 event: models.TollEvent) -> str:
    pay_link = f"{BACKEND_URL}/pay/{event.id}"
    return (
        f"[{SMS_SENDER_NAME}] REMINDER: Toll for {vehicle.plate} still unpaid. "
        f"BDT {_total_due(event):.0f}. Pay now: {pay_link}  or *999#. "
        f"Late fee will apply soon. Ref #{event.id}."
    )


def tpl_late_fee(vehicle: models.Vehicle,
                 event: models.TollEvent) -> str:
    pay_link = f"{BACKEND_URL}/pay/{event.id}"
    return (
        f"[{SMS_SENDER_NAME}] LATE FEE applied on {vehicle.plate}. "
        f"Total now BDT {_total_due(event):.0f} "
        f"(toll {event.amount_bdt:.0f} + late fee {event.late_fee_bdt:.0f}). "
        f"Pay immediately: {pay_link}  Ref #{event.id}."
    )


def tpl_fine(vehicle: models.Vehicle,
             event: models.TollEvent) -> str:
    pay_link = f"{BACKEND_URL}/pay/{event.id}"
    return (
        f"[{SMS_SENDER_NAME}] FINE imposed on {vehicle.plate}. "
        f"Total BDT {_total_due(event):.0f} "
        f"(toll {event.amount_bdt:.0f} + late {event.late_fee_bdt:.0f} "
        f"+ fine {event.fine_bdt:.0f}). "
        f"BRTA block pending. Pay: {pay_link}  Ref #{event.id}."
    )


def tpl_brta_block(vehicle: models.Vehicle,
                   event: models.TollEvent) -> str:
    pay_link = f"{BACKEND_URL}/pay/{event.id}"
    return (
        f"[{SMS_SENDER_NAME}] BRTA BLOCK applied on {vehicle.plate}. "
        f"Vehicle fitness renewal, ownership transfer and route permit are "
        f"suspended until dues of BDT {_total_due(event):.0f} are cleared. "
        f"Settle now: {pay_link}  Ref #{event.id}."
    )


# ---------- dispatch ----------

def _send_telegram(body: str) -> bool:
    """Fire a Telegram message. Returns True on success. Best-effort."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": body},
            timeout=5,
        )
        return r.ok
    except requests.RequestException:
        return False


def send_notification(
    db: Session,
    *,
    to_phone: str,
    body: str,
    kind: str,
    plate: str | None = None,
) -> models.SmsMessage:
    """Persist an SMS and (optionally) fire a Telegram mirror in a thread."""
    msg = models.SmsMessage(
        to_phone=to_phone or "UNKNOWN",
        plate=plate,
        kind=kind,
        body=body,
        telegram_sent=False,
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    db.flush()  # we need msg.id for the log line
    msg_id = msg.id

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        # Fire in a thread so the HTTP request doesn't block the API response.
        # We cannot update `msg.telegram_sent` from the thread safely without
        # a fresh session; for the demo we optimistically mark it true when
        # the call actually succeeds using a second short-lived session.
        def _bg(m_id: int, m_body: str):
            ok = _send_telegram(m_body)
            if ok:
                from backend.db import SessionLocal
                s2 = SessionLocal()
                try:
                    row = s2.get(models.SmsMessage, m_id)
                    if row is not None:
                        row.telegram_sent = True
                        s2.commit()
                finally:
                    s2.close()
        threading.Thread(target=_bg, args=(msg_id, body), daemon=True).start()

    print(f"[SMS -> {msg.to_phone}] ({kind}) {body}")
    return msg
