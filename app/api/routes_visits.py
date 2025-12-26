from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.deps import get_current_user, role_required
from app.models.user import UserRole, User
from app.models.patient import Patient
from app.models.visit import Visit, VisitStatus, PaymentStatus
from app.models.procedure import Procedure

from app.schemas.visit import (
    VisitCreate,
    VisitRead,
    VisitCreateByDentist,
    VisitCompleteByDentist,
)

router = APIRouter(prefix="/visits", tags=["visits"])

DEFAULT_VISIT_DURATION_MIN = 30


# -----------------------------
# Helpers
# -----------------------------
async def _get_duration_minutes(
    db: AsyncSession,
    *,
    duration_minutes: Optional[int],
    procedure_id: Optional[int],
) -> int:
    """
    Правило:
    1) если duration_minutes передали — используем
    2) иначе если есть procedure_id и у процедуры есть duration_minutes — используем
    3) иначе DEFAULT_VISIT_DURATION_MIN
    """
    if duration_minutes and duration_minutes > 0:
        return int(duration_minutes)

    if procedure_id:
        proc = await db.get(Procedure, procedure_id)
        if proc and proc.duration_minutes and proc.duration_minutes > 0:
            return int(proc.duration_minutes)

    return DEFAULT_VISIT_DURATION_MIN


async def _check_overlap(
    db: AsyncSession,
    *,
    dentist_id: int,
    start_dt: datetime,
    end_dt: datetime,
    exclude_visit_id: Optional[int] = None,
) -> None:
    """
    Проверяем пересечение интервалов:
    новый [start_dt, end_dt]
    конфликт если start_dt < existing_end AND end_dt > existing_start

    existing_end = existing.date + duration
    duration берём:
      - existing.duration_minutes
      - иначе existing.procedure.duration_minutes
      - иначе DEFAULT_VISIT_DURATION_MIN
    """
    stmt = select(Visit).where(Visit.dentist_id == dentist_id)
    if exclude_visit_id:
        stmt = stmt.where(Visit.id != exclude_visit_id)

    res = await db.execute(stmt)
    visits = res.scalars().all()

    for v in visits:
        existing_duration = await _get_duration_minutes(
            db,
            duration_minutes=v.duration_minutes,
            procedure_id=v.procedure_id,
        )
        v_start = v.date
        v_end = v.date + timedelta(minutes=existing_duration)

        if start_dt < v_end and end_dt > v_start:
            raise HTTPException(
                status_code=409,
                detail=f"Пересечение расписания: есть визит {v.id} с {v_start} до {v_end}",
            )


# -----------------------------
# Public endpoints
# -----------------------------
@router.get("/", response_model=List[VisitRead])
async def list_visits(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    dentist_id: Optional[int] = Query(None),
    patient_id: Optional[int] = Query(None),
    visit_status: Optional[VisitStatus] = Query(None),
):
    """
    Список визитов с фильтрами.
    """
    stmt = select(Visit)
    conditions = []

    if date_from:
        conditions.append(Visit.date >= date_from)
    if date_to:
        conditions.append(Visit.date <= date_to)
    if dentist_id:
        conditions.append(Visit.dentist_id == dentist_id)
    if patient_id:
        conditions.append(Visit.patient_id == patient_id)
    if visit_status:
        conditions.append(Visit.visit_status == visit_status)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(Visit.date.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{visit_id}", response_model=VisitRead)
async def get_visit(
    visit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Получить визит по id.
    """
    visit = await db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Визит не найден")
    return visit


# -----------------------------
# Manager creates visit (for any dentist)
# -----------------------------
@router.post("/", response_model=VisitRead)
async def create_visit_by_manager(
    data: VisitCreate,
    db: AsyncSession = Depends(get_db),
    manager=Depends(role_required(UserRole.manager)),
):
    """
    Создание визита менеджером (может выбрать любого стоматолога).
    """
    patient = await db.get(Patient, data.patient_id)
    if not patient:
        raise HTTPException(404, "Пациент не найден")

    dentist = await db.get(User, data.dentist_id)
    if not dentist or dentist.role != UserRole.dentist:
        raise HTTPException(400, "Стоматолог не найден или роль некорректна")

    duration = await _get_duration_minutes(
        db,
        duration_minutes=getattr(data, "duration_minutes", None),
        procedure_id=getattr(data, "procedure_id", None),
    )
    start_dt = data.date
    end_dt = data.date + timedelta(minutes=duration)

    await _check_overlap(db, dentist_id=data.dentist_id, start_dt=start_dt, end_dt=end_dt)

    # Важно: по твоему ТЗ сумма может быть сначала null/0 и ставится после осмотра.
    # Поэтому при создании визита менеджером можно поставить total_amount=None
    # или если ты передал total_amount — сохранить.
    total_amount = getattr(data, "total_amount", None)
    paid_amount = getattr(data, "paid_amount", 0.0) or 0.0
    remaining = 0.0
    if total_amount is not None:
        remaining = max(0.0, float(total_amount) - float(paid_amount))

    # статусы
    visit_status = getattr(data, "visit_status", VisitStatus.scheduled)
    payment_status = getattr(data, "payment_status", PaymentStatus.unpaid)
    if total_amount is None or total_amount == 0:
        payment_status = PaymentStatus.unpaid

    visit = Visit(
        patient_id=data.patient_id,
        dentist_id=data.dentist_id,
        procedure_id=getattr(data, "procedure_id", None),
        procedure=getattr(data, "procedure", None),
        duration_minutes=getattr(data, "duration_minutes", None),
        date=data.date,
        total_amount=total_amount,
        paid_amount=paid_amount,
        remaining=remaining,
        payment_status=payment_status,
        visit_status=visit_status,
    )

    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return visit


# -----------------------------
# Dentist creates visit (ONLY for himself)
# -----------------------------
@router.post("/dentist", response_model=VisitRead)
async def create_visit_by_dentist(
    data: VisitCreateByDentist,
    db: AsyncSession = Depends(get_db),
    dentist=Depends(role_required(UserRole.dentist)),
):
    """
    Стоматолог создаёт визит ТОЛЬКО себе.
    Дата может быть в прошлом (по твоему ТЗ — да).
    """
    patient = await db.get(Patient, data.patient_id)
    if not patient:
        raise HTTPException(404, "Пациент не найден")

    duration = await _get_duration_minutes(
        db,
        duration_minutes=data.duration_minutes,
        procedure_id=data.procedure_id,
    )
    start_dt = data.date
    end_dt = data.date + timedelta(minutes=duration)

    await _check_overlap(db, dentist_id=dentist.id, start_dt=start_dt, end_dt=end_dt)

    # Важно: стоматолог создаёт визит без суммы (после осмотра)
    visit = Visit(
        patient_id=data.patient_id,
        dentist_id=dentist.id,
        procedure_id=data.procedure_id,
        procedure=data.procedure,
        duration_minutes=data.duration_minutes,
        date=data.date,
        total_amount=None,      # сначала NULL
        paid_amount=0.0,
        remaining=0.0,
        payment_status=PaymentStatus.unpaid,
        visit_status=VisitStatus.scheduled,
    )

    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return visit


# -----------------------------
# Dentist completes visit: sets total_amount + duration_minutes
# -----------------------------
@router.patch("/{visit_id}/complete", response_model=VisitRead)
async def complete_visit_by_dentist(
    visit_id: int,
    data: VisitCompleteByDentist,
    db: AsyncSession = Depends(get_db),
    dentist=Depends(role_required(UserRole.dentist)),
):
    """
    Стоматолог завершает визит:
    - может завершить ТОЛЬКО свой визит
    - указывает total_amount (после осмотра)
    - может обновить duration_minutes
    - меняет visit_status -> completed
    - payment_status пересчитывается автоматически (оплата всё равно делает менеджер)
    """
    visit = await db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Визит не найден")

    if visit.dentist_id != dentist.id:
        raise HTTPException(403, "Нельзя завершать визит другого врача")

    # можно поменять длительность
    if data.duration_minutes is not None:
        if data.duration_minutes <= 0:
            raise HTTPException(400, "duration_minutes должен быть > 0")
        visit.duration_minutes = int(data.duration_minutes)

    # ставим сумму после осмотра
    if data.total_amount < 0:
        raise HTTPException(400, "total_amount не может быть отрицательным")

    visit.total_amount = float(data.total_amount)

    # пересчитываем remaining
    paid = float(visit.paid_amount or 0.0)
    total = float(visit.total_amount or 0.0)
    visit.remaining = max(0.0, total - paid)

    # статус визита
    visit.visit_status = VisitStatus.completed

    # статус оплаты (оплаты делает менеджер, но статус должен быть честный)
    if visit.remaining == 0 and total > 0:
        visit.payment_status = PaymentStatus.paid
    elif 0 < visit.remaining < total:
        visit.payment_status = PaymentStatus.partial
    else:
        visit.payment_status = PaymentStatus.unpaid

    await db.commit()
    await db.refresh(visit)
    return visit


# -----------------------------
# Update visit status (manager/admin/dentist rules simplified)
# -----------------------------
@router.patch("/{visit_id}/status", response_model=VisitRead)
async def update_visit_status(
    visit_id: int,
    visit_status: VisitStatus,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Обновить статус визита:
    - manager/admin: любой визит
    - dentist: только свой
    """
    visit = await db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Визит не найден")

    role = current_user.role
    if role == UserRole.dentist and visit.dentist_id != current_user.id:
        raise HTTPException(403, "Нельзя менять статус чужого визита")

    visit.visit_status = visit_status
    await db.commit()
    await db.refresh(visit)
    return visit
