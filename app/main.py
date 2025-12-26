from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api import routes_auth, routes_patients, routes_dashboard, routes_visits, routes_payments

settings = get_settings()

app = FastAPI(title=settings.app_name)

# CORS (нужно для Flutter Web и для любых запросов из браузера)
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "https://dental.inbrain.kz",
    "https://b1d6fa20-0f2f-4ff7-8ee9-ddb4fc2c4c3b.lovableproject.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router)
app.include_router(routes_patients.router)
app.include_router(routes_visits.router)
app.include_router(routes_payments.router)
app.include_router(routes_dashboard.router)
