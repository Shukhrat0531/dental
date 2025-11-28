from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.visit import Visit, VisitStatus, PaymentStatus
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.visit import VisitCreate, VisitRead
from app.core.deps import get_current_user, role_required

router = APIRouter(prefix="/visits", tags=["visits"])


@router.get("/", response_model=List[VisitRead])
async def list_visits(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    dentist_id: Optional[int] = Query(None),
    patient_id: Optional[int] = Query(None),
    visit_status: Optional[VisitStatus] = Query(None),
):
    """Список визитов с фильтрами."""
    stmt = select(Visit)

    conditions = []

    if date_from:
        conditions.append(Visit.date >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        conditions.append(Visit.date <= datetime.combine(date_to, datetime.max.time()))
    if dentist_id:
        conditions.append(Visit.dentist_id == dentist_id)
    if patient_id:
        conditions.append(Visit.patient_id == patient_id)
    if visit_status:
        conditions.append(Visit.visit_status == visit_status)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt.order_by(Visit.date.desc()))
    visits = result.scalars().all()
    return visits


@router.post("/", response_model=VisitRead)
async def create_visit(
    data: VisitCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(role_required(UserRole.manager)),  # визит создаёт менеджер
):
    """Создание визита (записи)."""
    # проверим, что пациент и стоматолог существуют
    patient = await db.get(Patient, data.patient_id)
    if not patient:
        raise HTTPException(404, "Пациент не найден")

    dentist = await db.get(User, data.dentist_id)
    if not dentist or dentist.role != UserRole.dentist:
        raise HTTPException(400, "Стоматолог не найден или некорректная роль")

    visit = Visit(
        patient_id=data.patient_id,
        dentist_id=data.dentist_id,
        procedure=data.procedure,
        date=data.date,
        total_amount=data.total_amount,
        paid_amount=data.paid_amount,
        remaining=data.remaining,
        payment_status=data.payment_status,
        visit_status=data.visit_status,
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return visit


@router.get("/{visit_id}", response_model=VisitRead)
async def get_visit(
    visit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    visit = await db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Визит не найден")
    return visit


@router.patch("/{visit_id}/status", response_model=VisitRead)
async def update_visit_status(
    visit_id: int,
    visit_status: VisitStatus,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Обновление статуса визита (запланирован / в процессе / завершён)."""
    visit = await db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Визит не найден")

    visit.visit_status = visit_status
    await db.commit()
    await db.refresh(visit)
    return visit
