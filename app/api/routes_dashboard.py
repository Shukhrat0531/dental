from datetime import datetime, timedelta, date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.visit import Visit, VisitStatus
from app.models.payment import Payment
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.dashboard import (
    AdminDashboard,
    AdminFinanceItem,
    AdminStaffItem,
    DentistDashboard,
    DentistActiveVisit,
    VisitShort,
    ManagerDashboard,
    ManagerScheduleItem,
)
from app.core.deps import role_required, get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------- ADMIN ----------

@router.get("/admin", response_model=AdminDashboard)
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required(UserRole.admin)),
):
    total_visits = await db.scalar(select(func.count(Visit.id)))
    total_patients = await db.scalar(select(func.count(Patient.id)))
    total_income = await db.scalar(select(func.coalesce(func.sum(Payment.amount), 0.0)))
    total_debt = await db.scalar(select(func.coalesce(func.sum(Visit.remaining), 0.0)))

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    prev_month_ago = month_ago - timedelta(days=30)

    income_week = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(Payment.date >= week_ago)
    )
    income_month = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(Payment.date >= month_ago)
    )
    prev_month_income = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(
            Payment.date >= prev_month_ago, Payment.date < month_ago
        )
    )

    if prev_month_income == 0:
        percent_change = 100.0 if income_month and income_month > 0 else 0.0
    else:
        percent_change = float(income_month - prev_month_income) / float(prev_month_income) * 100.0

    return AdminDashboard(
        totalVisits=int(total_visits or 0),
        totalPatients=int(total_patients or 0),
        totalIncome=float(total_income or 0),
        totalDebt=float(total_debt or 0),
        incomeWeek=float(income_week or 0),
        incomeMonth=float(income_month or 0),
        percentChange=float(percent_change),
    )


@router.get("/admin/finance", response_model=List[AdminFinanceItem])
async def admin_finance(
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required(UserRole.admin)),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """
    Финансы по дням: AdminFinanceModel
    """
    # по умолчанию последние 30 дней
    if not date_to:
        date_to = datetime.utcnow().date()
    if not date_from:
        date_from = date_to - timedelta(days=30)

    stmt = (
        select(
            func.date(Payment.date).label("dt"),
            func.coalesce(func.sum(Payment.amount), 0.0).label("income"),
            func.coalesce(func.sum(Payment.amount), 0.0).label("paid"),
            func.coalesce(
                func.sum(
                    func.case(
                        (Visit.remaining > 0, Visit.remaining),
                        else_=0.0,
                    )
                ),
                0.0,
            ).label("debt"),
            func.count(Visit.id).label("visits_count"),
            func.count(Patient.id).label("patients_count"),
        )
        .select_from(Payment)
        .join(Visit, Visit.id == Payment.visit_id)
        .join(Patient, Patient.id == Payment.patient_id)
        .where(
            and_(
                Payment.date >= datetime.combine(date_from, datetime.min.time()),
                Payment.date <= datetime.combine(date_to, datetime.max.time()),
            )
        )
        .group_by(func.date(Payment.date))
        .order_by(func.date(Payment.date))
    )

    result = await db.execute(stmt)
    rows = result.all()

    items: List[AdminFinanceItem] = []
    for row in rows:
        items.append(
            AdminFinanceItem(
                date=row.dt,
                income=row.income,
                paid=row.paid,
                debt=row.debt,
                visitsCount=row.visits_count,
                patientsCount=row.patients_count,
            )
        )

    return items


@router.get("/admin/staff", response_model=List[AdminStaffItem])
async def admin_staff(
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required(UserRole.admin)),
):
    """
    Список персонала (стоматологи + менеджеры) под AdminStaffModel.
    """
    result = await db.execute(
        select(User).where(User.role.in_([UserRole.dentist, UserRole.manager]))
    )
    users = result.scalars().all()

    items: List[AdminStaffItem] = []
    for u in users:
        items.append(
            AdminStaffItem(
                id=u.id,
                fullName=u.full_name,
                role="Стоматолог" if u.role == UserRole.dentist else "Менеджер",
                phone=u.phone,
                email=u.email,
                isActive=u.is_active,
            )
        )
    return items


# ---------- DENTIST ----------

@router.get("/dentist", response_model=DentistDashboard)
async def dentist_dashboard(
    db: AsyncSession = Depends(get_db),
    dentist=Depends(role_required(UserRole.dentist)),
):
    """
    Дашборд стоматолога:
    - визиты на сегодня
    - доход за неделю/месяц
    - активный визит
    """
    today = datetime.utcnow().date()
    start_today = datetime.combine(today, datetime.min.time())
    end_today = datetime.combine(today, datetime.max.time())

    # визиты текущего стоматолога на сегодня
    result = await db.execute(
        select(Visit)
        .where(
            and_(
                Visit.dentist_id == dentist.id,
                Visit.date >= start_today,
                Visit.date <= end_today,
            )
        )
        .order_by(Visit.date)
    )
    today_visits = result.scalars().all()

    # доход стоматолога за неделю/месяц (по связанным платежам)
    week_ago = datetime.utcnow() - timedelta(days=7)
    month_ago = datetime.utcnow() - timedelta(days=30)

    income_week = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(
            and_(
                Payment.visit_id == Visit.id,
            )
        )
    )
    # упрощённо считаем по всем платежам этого стоматолога
    income_week = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0))
        .join(Visit, Visit.id == Payment.visit_id)
        .where(
            and_(
                Visit.dentist_id == dentist.id,
                Payment.date >= week_ago,
            )
        )
    )
    income_month = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0))
        .join(Visit, Visit.id == Payment.visit_id)
        .where(
            and_(
                Visit.dentist_id == dentist.id,
                Payment.date >= month_ago,
            )
        )
    )

    # динамика (для простоты сравнение с предыдущим месяцем)
    prev_month_ago = month_ago - timedelta(days=30)
    prev_month_income = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0))
        .join(Visit, Visit.id == Payment.visit_id)
        .where(
            and_(
                Visit.dentist_id == dentist.id,
                Payment.date >= prev_month_ago,
                Payment.date < month_ago,
            )
        )
    )

    if prev_month_income == 0:
        percent_change = 100.0 if income_month and income_month > 0 else 0.0
    else:
        percent_change = float(income_month - prev_month_income) / float(prev_month_income) * 100.0

    # активный визит (первый "в процессе")
    active = next((v for v in today_visits if v.visit_status == VisitStatus.in_progress), None)

    active_visit: Optional[DentistActiveVisit] = None
    if active:
        active_visit = DentistActiveVisit(
            visitId=active.id,
            patientName=str(active.patient_id),  # при желании можно сделать join на Patient
            procedure=active.procedure,
            totalAmount=active.total_amount,
            paidAmount=active.paid_amount,
            remaining=active.remaining,
            visitTime=active.date,
            isStarted=active.visit_status == VisitStatus.in_progress,
        )

    today_short: List[VisitShort] = []
    for v in today_visits:
        today_short.append(
            VisitShort(
                id=v.id,
                patientName=str(v.patient_id),
                procedure=v.procedure,
                date=v.date,
                totalAmount=v.total_amount,
                paidAmount=v.paid_amount,
                remaining=v.remaining,
                paymentStatus=v.payment_status.value,
                visitStatus=v.visit_status.value,
            )
        )

    return DentistDashboard(
        totalVisitsToday=len(today_visits),
        incomeWeek=float(income_week or 0),
        incomeMonth=float(income_month or 0),
        percentChange=float(percent_change),
        activeVisit=active_visit,
        todayVisits=today_short,
    )


# ---------- MANAGER ----------

@router.get("/manager", response_model=ManagerDashboard)
async def manager_dashboard(
    db: AsyncSession = Depends(get_db),
    manager=Depends(role_required(UserRole.manager)),
):
    today = datetime.utcnow().date()
    start_today = datetime.combine(today, datetime.min.time())
    end_today = datetime.combine(today, datetime.max.time())

    # визиты сегодня
    result = await db.execute(
        select(Visit).where(
            and_(
                Visit.date >= start_today,
                Visit.date <= end_today,
            )
        )
    )
    visits_today = result.scalars().all()

    total_visits_today = len(visits_today)
    patients_ids = {v.patient_id for v in visits_today}
    total_patients_today = len(patients_ids)

    total_income_today = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(
            and_(
                Payment.date >= start_today,
                Payment.date <= end_today,
            )
        )
    )

    total_debt = await db.scalar(select(func.coalesce(func.sum(Visit.remaining), 0.0)))

    upcoming_visits = sum(1 for v in visits_today if v.visit_status == VisitStatus.scheduled)
    completed_visits = sum(1 for v in visits_today if v.visit_status == VisitStatus.completed)

    return ManagerDashboard(
        totalVisitsToday=total_visits_today,
        totalPatientsToday=total_patients_today,
        totalIncomeToday=float(total_income_today or 0),
        totalDebt=float(total_debt or 0),
        upcomingVisits=upcoming_visits,
        completedVisits=completed_visits,
    )


@router.get("/manager/schedule", response_model=ManagerScheduleItem)
async def manager_schedule(
    db: AsyncSession = Depends(get_db),
    manager=Depends(role_required(UserRole.manager)),
    date_value: Optional[date] = Query(None, alias="date"),
):
    """
    Расписание на день: ManagerScheduleModel
    """
    if not date_value:
        date_value = datetime.utcnow().date()

    start_day = datetime.combine(date_value, datetime.min.time())
    end_day = datetime.combine(date_value, datetime.max.time())

    result = await db.execute(
        select(Visit)
        .where(
            and_(
                Visit.date >= start_day,
                Visit.date <= end_day,
            )
        )
        .order_by(Visit.date)
    )
    visits = result.scalars().all()

    visits_short: List[VisitShort] = []
    for v in visits:
        visits_short.append(
            VisitShort(
                id=v.id,
                patientName=str(v.patient_id),
                procedure=v.procedure,
                date=v.date,
                totalAmount=v.total_amount,
                paidAmount=v.paid_amount,
                remaining=v.remaining,
                paymentStatus=v.payment_status.value,
                visitStatus=v.visit_status.value,
            )
        )

    return ManagerScheduleItem(
        date=datetime.combine(date_value, datetime.min.time()),
        visits=visits_short,
    )
