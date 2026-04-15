"""Business-logic helpers shared by the JSON API and the HTML payment pages."""
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend import models
from backend.notifications import (
    send_notification, tpl_payment_confirmation,
)
from config import SMS_SENDER_NAME


class PaymentError(Exception):
    pass


def event_total_due(event: models.TollEvent) -> float:
    return (event.amount_bdt or 0.0) + (event.late_fee_bdt or 0.0) + (event.fine_bdt or 0.0)


def mark_event_paid(db: Session, event_id: int,
                    channel: str = "manual") -> models.TollEvent:
    """Mark a toll event PAID, send confirmation SMS, auto-unblock the
    vehicle if no unpaid events remain, and commit.

    Raises PaymentError if the event doesn't exist or is already paid.
    `channel` is free-form: 'bkash', 'nagad', 'ussd', 'api', etc.
    """
    event = db.get(models.TollEvent, event_id)
    if event is None:
        raise PaymentError(f"Event #{event_id} not found")
    if event.status == "PAID":
        raise PaymentError(f"Event #{event_id} already paid")

    paid_total = event_total_due(event)
    event.status = "PAID"
    event.paid_at = datetime.utcnow()
    db.flush()

    vehicle = db.get(models.Vehicle, event.plate)

    # Payment confirmation SMS.
    body = tpl_payment_confirmation(vehicle, event) if vehicle else \
        f"[{SMS_SENDER_NAME}] Payment received: BDT {paid_total:.0f} " \
        f"(Ref #{event.id}). Thank you."
    send_notification(
        db,
        to_phone=(vehicle.phone if vehicle else ""),
        body=body,
        kind="PAYMENT_CONFIRMATION",
        plate=event.plate,
    )

    # If this was the last outstanding event and the vehicle is BRTA-blocked,
    # lift the block.
    if vehicle is not None and vehicle.brta_blocked:
        remaining = db.scalar(
            select(func.count(models.TollEvent.id))
            .where(models.TollEvent.plate == vehicle.plate,
                   models.TollEvent.status != "PAID")
        ) or 0
        if remaining == 0:
            vehicle.brta_blocked = False
            send_notification(
                db,
                to_phone=vehicle.phone,
                body=(f"[{SMS_SENDER_NAME}] BRTA block lifted for "
                      f"{vehicle.plate}. All dues cleared. Thank you."),
                kind="BRTA_UNBLOCK",
                plate=vehicle.plate,
            )
            print(f"[enforcement] {vehicle.plate}: BRTA block lifted")

    db.commit()
    db.refresh(event)
    print(f"[PAID via {channel}] event #{event.id} BDT {paid_total:.0f}")
    return event
