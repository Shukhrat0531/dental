from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

# AdminDashboardModel
class AdminDashboard(BaseModel):
    totalVisits: int
    totalPatients: int
    totalIncome: float
    totalDebt: float
    incomeWeek: float
    incomeMonth: float
    percentChange: float


class AdminFinanceItem(BaseModel):
    date: datetime
    income: float
    paid: float
    debt: float
    visitsCount: int
    patientsCount: int


class AdminStaffItem(BaseModel):
    id: int
    fullName: str
    role: str
    phone: str
    email: str
    isActive: bool


# Dentist
class DentistActiveVisit(BaseModel):
    visitId: int
    patientName: str
    procedure: str
    totalAmount: float
    paidAmount: float
    remaining: float
    visitTime: datetime
    isStarted: bool = False


class VisitShort(BaseModel):
    id: int
    patientName: str
    procedure: str
    date: datetime
    totalAmount: float
    paidAmount: float
    remaining: float
    paymentStatus: str
    visitStatus: str


class DentistDashboard(BaseModel):
    totalVisitsToday: int
    incomeWeek: float
    incomeMonth: float
    percentChange: float
    activeVisit: Optional[DentistActiveVisit]
    todayVisits: List[VisitShort]


# Manager models
class ManagerDashboard(BaseModel):
    totalVisitsToday: int
    totalPatientsToday: int
    totalIncomeToday: float
    totalDebt: float
    upcomingVisits: int
    completedVisits: int


class ManagerPaymentItem(BaseModel):
    id: int
    visitId: int
    procedure: str
    visitDate: datetime
    total: float
    alreadyPaid: float
    remaining: float
    paymentAmount: float
    method: str
    newRemaining: float


class ManagerScheduleItem(BaseModel):
    date: datetime
    visits: list[VisitShort]
