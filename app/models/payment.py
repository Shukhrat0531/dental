import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Float, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class PaymentMethod(str, enum.Enum):
    card = "карта"
    cash = "наличные"
    transfer = "перевод"


class PaymentType(str, enum.Enum):
    full = "полная"
    partial = "частичная"


class Payment(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"))

    amount: Mapped[float] = mapped_column(Float)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    date: Mapped[datetime] = mapped_column(DateTime)

    payment_type: Mapped[PaymentType] = mapped_column(Enum(PaymentType))

    visit = relationship("Visit", backref="payments")
    patient = relationship("Patient", backref="payments")
