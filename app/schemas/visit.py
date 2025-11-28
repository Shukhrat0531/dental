from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class PaymentStatus(str, Enum):
    paid = "оплачено"
    partial = "частично"
    unpaid = "не оплачено"


class VisitStatus(str, Enum):
    scheduled = "запланирован"
    in_progress = "в процессе"
    completed = "завершён"


class VisitBase(BaseModel):
    patient_id: int
    dentist_id: int
    procedure: str
    date: datetime
    total_amount: float
    paid_amount: float = 0.0
    remaining: float
    payment_status: PaymentStatus
    visit_status: VisitStatus


class VisitCreate(VisitBase):
    pass


class VisitRead(VisitBase):
    id: int

    class Config:
        from_attributes = True
