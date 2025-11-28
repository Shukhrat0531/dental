from fastapi import FastAPI
from app.api import routes_auth, routes_patients, routes_dashboard, routes_visits, routes_payments
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(routes_auth.router)
app.include_router(routes_patients.router)
app.include_router(routes_visits.router)
app.include_router(routes_payments.router)
app.include_router(routes_dashboard.router)
