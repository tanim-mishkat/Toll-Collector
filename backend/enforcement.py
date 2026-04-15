"""Background enforcement loop.

Runs every ENFORCEMENT_TICK_SEC seconds. For each non-paid event, computes
its age and advances its status through the pipeline:

    UNPAID -> REMINDED -> LATE -> FINED -> BLOCKED

At LATE a late fee is added; at FINED a fine is added; at BLOCKED the
vehicle is flagged (brta_blocked=True) — this simulates the BRTA renewal
hold that is the strongest enforcement lever in the proposal.

Every transition fires an SMS via the notifications module.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import (
    ENFORCEMENT_ENABLED, ENFORCEMENT_TICK_SEC, ENFORCEMENT_TIMINGS_SEC,
    LATE_FEE_MULTIPLIER, FINE_MULTIPLIER,
)
from backend import models
from backend.db import SessionLocal
from backend.notifications import (
    send_notification,
    tpl_reminder, tpl_late_fee, tpl_fine, tpl_brta_block,
)


# Order matters: escalation proceeds left-to-right.
ESCALATION = ["UNPAID", "REMINDED", "LATE", "FINED", "BLOCKED"]


def _target_status(age_sec: float) -> str:
    """Highest status an event of this age should be in."""
    target = "UNPAID"
    for s in ("REMINDED", "LATE", "FINED", "BLOCKED"):
        if age_sec >= ENFORCEMENT_TIMINGS_SEC[s]:
            target = s
    return target


def _apply_transition(db: Session, event: models.TollEvent,
                      new_status: str) -> None:
    old = event.status
    event.status = new_status
    vehicle = db.get(models.Vehicle, event.plate)

    if new_status == "LATE" and event.late_fee_bdt == 0:
        event.late_fee_bdt = event.amount_bdt * LATE_FEE_MULTIPLIER
    if new_status == "FINED" and event.fine_bdt == 0:
        # Ensure late fee also present (if escalating straight through)
        if event.late_fee_bdt == 0:
            event.late_fee_bdt = event.amount_bdt * LATE_FEE_MULTIPLIER
        event.fine_bdt = event.amount_bdt * FINE_MULTIPLIER
    if new_status == "BLOCKED":
        if event.late_fee_bdt == 0:
            event.late_fee_bdt = event.amount_bdt * LATE_FEE_MULTIPLIER
        if event.fine_bdt == 0:
            event.fine_bdt = event.amount_bdt * FINE_MULTIPLIER
        if vehicle is not None:
            vehicle.brta_blocked = True

    # Need fresh field values for the SMS template.
    db.flush()

    if vehicle is None:
        return

    tpl = {
        "REMINDED": tpl_reminder,
        "LATE": tpl_late_fee,
        "FINED": tpl_fine,
        "BLOCKED": tpl_brta_block,
    }.get(new_status)
    if tpl is None:
        return

    send_notification(
        db,
        to_phone=vehicle.phone,
        body=tpl(vehicle, event),
        kind={"REMINDED": "REMINDER",
              "LATE": "LATE_FEE",
              "FINED": "FINE",
              "BLOCKED": "BRTA_BLOCK"}[new_status],
        plate=event.plate,
    )

    print(f"[enforcement] {event.plate} #{event.id}: {old} -> {new_status}")


def run_cycle() -> dict:
    """Run one enforcement sweep. Returns summary counters."""
    counts = {"REMINDED": 0, "LATE": 0, "FINED": 0, "BLOCKED": 0}
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        events = db.scalars(
            select(models.TollEvent)
            .where(models.TollEvent.status.in_(ESCALATION))
        ).all()
        for e in events:
            age = (now - e.created_at).total_seconds()
            target = _target_status(age)
            if target == e.status:
                continue
            # Advance one step at a time so each transition emits its own SMS.
            current_idx = ESCALATION.index(e.status)
            target_idx = ESCALATION.index(target)
            for step in range(current_idx + 1, target_idx + 1):
                step_status = ESCALATION[step]
                _apply_transition(db, e, step_status)
                if step_status in counts:
                    counts[step_status] += 1
        db.commit()
    except Exception as err:
        db.rollback()
        print(f"[enforcement] cycle error: {err!r}")
    finally:
        db.close()
    return counts


def _loop() -> None:
    while True:
        try:
            run_cycle()
        except Exception as e:
            print(f"[enforcement] loop error: {e!r}")
        time.sleep(ENFORCEMENT_TICK_SEC)


_started = False


def start_background() -> None:
    global _started
    if _started or not ENFORCEMENT_ENABLED:
        return
    _started = True
    t = threading.Thread(target=_loop, daemon=True, name="enforcement")
    t.start()
    print(f"[enforcement] background thread started; tick="
          f"{ENFORCEMENT_TICK_SEC}s; thresholds={ENFORCEMENT_TIMINGS_SEC}")
