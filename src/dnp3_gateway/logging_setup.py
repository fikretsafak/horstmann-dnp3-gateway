"""Minimal yapilandirilabilir log ayarlari."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key.startswith("ctx_"):
                payload[key[4:]] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Root logger'i idempotent bicimde yapilandirir.

    Birden fazla cagri guvenlidir (handler cogaltilmaz).
    """

    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        if getattr(handler, "_dnp3_gateway", False):
            root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler._dnp3_gateway = True  # type: ignore[attr-defined]
    if fmt.strip().lower() == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-5s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    root.addHandler(handler)
    # AMQP baglanti ayrintilari: genelde sadece dnp3_gateway loglari yeterlidir
    logging.getLogger("pika").setLevel(logging.WARNING)
