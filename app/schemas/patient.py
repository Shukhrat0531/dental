from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class PatientBase(BaseModel):
    full_name: str
    phone: str
    email: Optional[EmailStr] = None


class PatientCreate(PatientBase):
    """Схема для создания пациента"""
    pass


class PatientRead(PatientBase):
    """Схема для ответа (чтения) пациента"""
    id: int
    total_debt: float
    last_visit_date: Optional[datetime]
    has_debt: bool

    class Config:
        from_attributes = True  # для работы с SQLAlchemy моделями (ORM mode)
