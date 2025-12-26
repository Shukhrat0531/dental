from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.visit import PaymentStatus, VisitStatus


# -------- Dentist --------
class VisitCreateByDentist(BaseModel):
    patient_id: int
    procedure_id: Optional[int] = None
    procedure: Optional[str] = None
    date: datetime
    duration_minutes: Optional[int] = None


class VisitCompleteByDentist(BaseModel):
    total_amount: float = Field(..., ge=0)
    duration_minutes: Optional[int] = Field(None, gt=0)


# -------- Manager --------
class VisitCreate(BaseModel):
    patient_id: int
    dentist_id: int
    procedure_id: Optional[int] = None
    procedure: Optional[str] = None
    date: datetime
    duration_minutes: Optional[int] = None

    # сумма по твоему ТЗ сначала может быть null,
    # поэтому менеджер может не указывать.
    total_amount: Optional[float] = Field(None, ge=0)


# -------- Read --------
class VisitRead(BaseModel):
    id: int
    patient_id: int
    dentist_id: int
    procedure_id: Optional[int] = None
    procedure: Optional[str] = None
    duration_minutes: Optional[int] = None
    date: datetime

    total_amount: Optional[float] = None
    paid_amount: float
    remaining: float

    payment_status: PaymentStatus
    visit_status: VisitStatus

    class Config:
        from_attributes = True
