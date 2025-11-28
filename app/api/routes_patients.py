from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.session import get_db
from app.schemas.patient import PatientCreate, PatientRead
from app.models.patient import Patient
from app.core.deps import get_current_user

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/", response_model=List[PatientRead])
async def list_patients(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Patient))
    return result.scalars().all()


@router.post("/", response_model=PatientRead)
async def create_patient(
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    patient = Patient(
        full_name=data.full_name,
        phone=data.phone,
        email=data.email,
    )
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient
