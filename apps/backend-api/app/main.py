from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alarms, auth, devices, health, telemetry, users
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import alarm, device, telemetry as telemetry_model, user  # noqa: F401

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(devices.router, prefix=settings.api_prefix)
app.include_router(telemetry.router, prefix=settings.api_prefix)
app.include_router(alarms.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)
