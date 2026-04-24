from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    consumer_name: Mapped[str] = mapped_column(String(80), index=True)
    message_id: Mapped[str] = mapped_column(String(120), index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
