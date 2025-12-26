from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Patient(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    total_debt: Mapped[float] = mapped_column(Float, default=0.0)
    # ВАЖНО: тут уже НЕ строка, а нормальный тип
    last_visit_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    has_debt: Mapped[bool] = mapped_column(Boolean, default=False)
