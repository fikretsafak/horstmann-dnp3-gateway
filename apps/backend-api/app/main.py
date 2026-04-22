from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import alarms, auth, devices, events, gateways, health, notification_settings, outbound_targets, telemetry, users
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import alarm, device, gateway, gateway_ingest_batch, notification_settings as notification_settings_model, outbound_target, system_event, telemetry as telemetry_model, user  # noqa: F401
from app.services.event_bus import event_bus
from app.services.worker_bootstrap import bootstrap_consumers

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
app.include_router(gateways.router, prefix=settings.api_prefix)
app.include_router(telemetry.router, prefix=settings.api_prefix)
app.include_router(alarms.router, prefix=settings.api_prefix)
app.include_router(events.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(notification_settings.router, prefix=settings.api_prefix)
app.include_router(outbound_targets.router, prefix=settings.api_prefix)


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
        connection.execute(
            text(
                "ALTER TABLE gateways ADD COLUMN IF NOT EXISTS upstream_url VARCHAR(500) "
                "DEFAULT 'https://central.example.com/api/v1/telemetry/gateway'"
            )
        )
        connection.execute(text("ALTER TABLE gateways ADD COLUMN IF NOT EXISTS batch_interval_sec INTEGER DEFAULT 5"))
        connection.execute(text("ALTER TABLE gateways ADD COLUMN IF NOT EXISTS max_devices INTEGER DEFAULT 200"))
        connection.execute(text("ALTER TABLE gateways ADD COLUMN IF NOT EXISTS device_code_prefix VARCHAR(80)"))
        connection.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS description VARCHAR(500)"))
        connection.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS gateway_code VARCHAR(50)"))
        connection.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS dnp3_address INTEGER DEFAULT 1"))
        connection.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS poll_interval_sec INTEGER DEFAULT 5"))
        connection.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS timeout_ms INTEGER DEFAULT 3000"))
        connection.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 2"))
        connection.execute(
            text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS signal_profile VARCHAR(80) DEFAULT 'horstmann_sn2_fixed'")
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS gateway_ingest_batches ("
                "id SERIAL PRIMARY KEY, "
                "gateway_code VARCHAR(50) NOT NULL, "
                "sequence_no INTEGER NOT NULL, "
                "sent_at TIMESTAMPTZ NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL, "
                "CONSTRAINT uq_gateway_sequence UNIQUE (gateway_code, sequence_no))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS notification_settings ("
                "id INTEGER PRIMARY KEY, "
                "smtp_enabled BOOLEAN NOT NULL DEFAULT FALSE, "
                "smtp_host VARCHAR(255) NOT NULL DEFAULT '', "
                "smtp_port INTEGER NOT NULL DEFAULT 25, "
                "smtp_username VARCHAR(255) NOT NULL DEFAULT '', "
                "smtp_password VARCHAR(255) NOT NULL DEFAULT '', "
                "smtp_from_email VARCHAR(255) NOT NULL DEFAULT '', "
                "sms_enabled BOOLEAN NOT NULL DEFAULT FALSE, "
                "sms_provider VARCHAR(80) NOT NULL DEFAULT 'mock', "
                "sms_api_url VARCHAR(500) NOT NULL DEFAULT '', "
                "sms_api_key VARCHAR(255) NOT NULL DEFAULT '')"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS outbound_targets ("
                "id SERIAL PRIMARY KEY, "
                "name VARCHAR(120) UNIQUE NOT NULL, "
                "protocol VARCHAR(20) NOT NULL, "
                "endpoint VARCHAR(500) NOT NULL, "
                "topic VARCHAR(255), "
                "event_filter VARCHAR(40) NOT NULL DEFAULT 'all', "
                "auth_header VARCHAR(255), "
                "auth_token VARCHAR(255), "
                "qos INTEGER NOT NULL DEFAULT 0, "
                "retain BOOLEAN NOT NULL DEFAULT FALSE, "
                "is_active BOOLEAN NOT NULL DEFAULT TRUE)"
            )
        )
    bootstrap_consumers(event_bus)
