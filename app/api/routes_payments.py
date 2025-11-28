from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func, join
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.payment import Payment, PaymentMethod, PaymentType
from app.models.visit import Visit, PaymentStatus
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.payment import PaymentCreate, PaymentRead
from app.schemas.dashboard import ManagerPaymentItem
from app.core.deps import get_current_user, role_required

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/", response_model=List[PaymentRead])
async def list_payments(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    patient_id: Optional[int] = Query(None),
    visit_id: Optional[int] = Query(None),
):
    stmt = select(Payment)
    conditions = []

    if date_from:
        conditions.append(Payment.date >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        conditions.append(Payment.date <= datetime.combine(date_to, datetime.max.time()))
    if patient_id:
        conditions.append(Payment.patient_id == patient_id)
    if visit_id:
        conditions.append(Payment.visit_id == visit_id)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt.order_by(Payment.date.desc()))
    return result.scalars().all()


@router.post("/", response_model=PaymentRead)
async def create_payment(
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(role_required(UserRole.manager)),
):
    """
    Создать платёж по визиту:
    - Создаёт запись в payments
    - Обновляет paid_amount, remaining, payment_status у Visit
    - Обновляет total_debt / has_debt у Patient
    """
    visit = await db.get(Visit, data.visit_id)
    if not visit:
        raise HTTPException(404, "Визит не найден")

    patient = await db.get(Patient, data.patient_id)
    if not patient:
        raise HTTPException(404, "Пациент не найден")

    payment = Payment(
        visit_id=data.visit_id,
        patient_id=data.patient_id,
        amount=data.amount,
        method=data.method,
        date=data.date,
        payment_type=data.payment_type,
    )
    db.add(payment)

    # обновляем суммы по визиту
    new_paid = visit.paid_amount + data.amount
    visit.paid_amount = new_paid
    visit.remaining = max(0.0, visit.total_amount - new_paid)

    if visit.remaining == 0:
        visit.payment_status = PaymentStatus.paid
    elif visit.remaining < visit.total_amount:
        visit.payment_status = PaymentStatus.partial
    else:
        visit.payment_status = PaymentStatus.unpaid

    # обновляем долг пациента (простая модель: сумма remaining по всем визитам)
    result = await db.execute(
        select(func.coalesce(func.sum(Visit.remaining), 0.0)).where(Visit.patient_id == patient.id)
    )
    total_debt = float(result.scalar() or 0.0)
    patient.total_debt = total_debt
    patient.has_debt = total_debt > 0

    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("/manager", response_model=List[ManagerPaymentItem])
async def list_manager_payments(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(role_required(UserRole.manager)),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """
    Список платежей для менеджера в виде ManagerPaymentModel.
    """
    j = join(Payment, Visit, Payment.visit_id == Visit.id)
    stmt = select(
        Payment.id,
        Payment.visit_id,
        Visit.procedure,
        Visit.date.label("visit_date"),
        Visit.total_amount.label("total"),
        Visit.paid_amount.label("already_paid"),
        Visit.remaining.label("remaining"),
        Payment.amount.label("payment_amount"),
        Payment.method,
        Visit.remaining.label("new_remaining"),  # на момент запроса
    ).select_from(j)

    conditions = []
    if date_from:
        conditions.append(Payment.date >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        conditions.append(Payment.date <= datetime.combine(date_to, datetime.max.time()))
    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(Payment.date.desc())

    result = await db.execute(stmt)
    rows = result.all()

    items: List[ManagerPaymentItem] = []
    for row in rows:
        items.append(
            ManagerPaymentItem(
                id=row.id,
                visitId=row.visit_id,
                procedure=row.procedure,
                visitDate=row.visit_date,
                total=row.total,
                alreadyPaid=row.already_paid,
                remaining=row.remaining,
                paymentAmount=row.payment_amount,
                method=row.method.value if hasattr(row.method, "value") else row.method,
                newRemaining=row.new_remaining,
            )
        )

    return items
