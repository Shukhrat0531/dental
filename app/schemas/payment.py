from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class PaymentMethod(str, Enum):
    card = "карта"
    cash = "наличные"
    transfer = "перевод"


class PaymentType(str, Enum):
    full = "полная"
    partial = "частичная"


class PaymentBase(BaseModel):
    visit_id: int
    patient_id: int
    amount: float
    method: PaymentMethod
    date: datetime
    payment_type: PaymentType


class PaymentCreate(PaymentBase):
    pass


class PaymentRead(PaymentBase):
    id: int

    class Config:
        from_attributes = True
