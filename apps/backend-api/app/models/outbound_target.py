from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OutboundTarget(Base):
    __tablename__ = "outbound_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    protocol: Mapped[str] = mapped_column(String(20), index=True)  # rest | mqtt
    endpoint: Mapped[str] = mapped_column(String(500))
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_filter: Mapped[str] = mapped_column(String(40), default="all", index=True)  # all | telemetry | alarm
    auth_header: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qos: Mapped[int] = mapped_column(Integer, default=0)
    retain: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
