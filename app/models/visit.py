import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Float, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class PaymentStatus(str, enum.Enum):
    paid = "оплачено"
    partial = "частично"
    unpaid = "не оплачено"


class VisitStatus(str, enum.Enum):
    scheduled = "запланирован"
    in_progress = "в процессе"
    completed = "завершён"


class Visit(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"))
    dentist_id: Mapped[int] = mapped_column(ForeignKey("user.id"))

    procedure: Mapped[str] = mapped_column(String(255))
    date: Mapped[datetime] = mapped_column(DateTime)

    total_amount: Mapped[float] = mapped_column(Float)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    remaining: Mapped[float] = mapped_column(Float)

    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus))
    visit_status: Mapped[VisitStatus] = mapped_column(Enum(VisitStatus))

    patient = relationship("Patient", backref="visits")
    dentist = relationship("User", backref="visits")
