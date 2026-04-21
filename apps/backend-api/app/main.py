from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import alarms, auth, devices, events, health, telemetry, users
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import alarm, device, system_event, telemetry as telemetry_model, user  # noqa: F401

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
app.include_router(events.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        # Keep Windows-first setup easy by ensuring newly added columns exist.
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(32)"))
        connection.execute(text("ALTER TABLE alarm_events ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(120)"))
        connection.execute(text("ALTER TABLE alarm_events ADD COLUMN IF NOT EXISTS acknowledged BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE alarm_events ADD COLUMN IF NOT EXISTS reset BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE alarm_events ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ"))
        connection.execute(text("ALTER TABLE alarm_events ADD COLUMN IF NOT EXISTS reset_at TIMESTAMPTZ"))
