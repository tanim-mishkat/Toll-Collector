"""Pydantic request/response schemas."""
from datetime import datetime
from pydantic import BaseModel, Field


class TollEventIn(BaseModel):
    plate: str = Field(min_length=2, max_length=32)
    gantry_id: str
    ocr_confidence: float = 0.0


class TollEventOut(BaseModel):
    id: int
    plate: str
    gantry_id: str
    amount_bdt: float
    late_fee_bdt: float = 0.0
    fine_bdt: float = 0.0
    total_due_bdt: float = 0.0
    status: str
    ocr_confidence: float
    created_at: datetime
    paid_at: datetime | None = None

    @classmethod
    def from_orm_with_total(cls, e):
        total = (e.amount_bdt or 0.0) + (e.late_fee_bdt or 0.0) + (e.fine_bdt or 0.0)
        return cls(
            id=e.id,
            plate=e.plate,
            gantry_id=e.gantry_id,
            amount_bdt=e.amount_bdt,
            late_fee_bdt=e.late_fee_bdt or 0.0,
            fine_bdt=e.fine_bdt or 0.0,
            total_due_bdt=total,
            status=e.status,
            ocr_confidence=e.ocr_confidence,
            created_at=e.created_at,
            paid_at=e.paid_at,
        )

    class Config:
        from_attributes = True


class VehicleOut(BaseModel):
    plate: str
    owner_name: str
    phone: str
    vehicle_class: str
    balance_bdt: float
    brta_blocked: bool
    registered: bool

    class Config:
        from_attributes = True


class VehicleDetail(VehicleOut):
    total_due_bdt: float
    unpaid_count: int
    recent_events: list[TollEventOut]


class TollEventCreated(BaseModel):
    event: TollEventOut
    vehicle: VehicleOut
    message: str


class PayResponse(BaseModel):
    event: TollEventOut
    message: str


class SmsOut(BaseModel):
    id: int
    to_phone: str
    plate: str | None
    kind: str
    body: str
    telegram_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True
