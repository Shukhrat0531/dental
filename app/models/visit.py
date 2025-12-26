import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PaymentStatus(str, enum.Enum):
    paid = "оплачено"
    partial = "частично"
    unpaid = "не оплачено"


class VisitStatus(str, enum.Enum):
    scheduled = "запланирован"
    in_progress = "в процессе"
    completed = "завершён"


class Visit(Base):
    __tablename__ = "visit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), index=True)
    dentist_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)

    procedure_id: Mapped[int | None] = mapped_column(
        ForeignKey("procedure.id"),
        nullable=True,
        index=True,
    )
    procedure: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )  # временно для совместимости

    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    date: Mapped[datetime] = mapped_column(DateTime, index=True)

    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    remaining: Mapped[float] = mapped_column(Float, default=0.0)

    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.unpaid,
    )
    visit_status: Mapped[VisitStatus] = mapped_column(
        Enum(VisitStatus, name="visit_status"),
        default=VisitStatus.scheduled,
    )
