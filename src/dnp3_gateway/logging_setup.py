"""Minimal yapilandirilabilir log ayarlari + sirli verileri redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

# Modul-level redaction registry: bilinen sirlari (token, parola) tutar.
# Logger formatter'i mesajlarda bu degerleri ***REDACTED*** ile yer degistirir.
# Boylece exception stack-trace'leri veya 3rd party library log'lari sirri
# kazara yazsa bile docker logs / ELK / Loki'ye gidemez.
_redacted_secrets: list[str] = []
_redacted_lock_safe = True  # GIL altinda atomic; lock gereksiz


def register_secret(value: str | None) -> None:
    """Verilen string'i redaction listesine ekler. Bos/None ignore.

    main.py boot'ta gateway_token, rabbitmq_url password vs. cagirir.
    """
    if not value:
        return
    v = value.strip()
    if len(v) < 4:
        # Cok kisa string'leri redact etme — false positive riski yuksek
        return
    if v not in _redacted_secrets:
        _redacted_secrets.append(v)


def _scrub_message(text: str) -> str:
    """Tum kayitli sirlari mesajdan redact eder."""
    if not text or not _redacted_secrets:
        return text
    # En uzundan basla (kisa secret uzun bir secret'in alt-string'i olabilir)
    for secret in sorted(_redacted_secrets, key=len, reverse=True):
        if secret and secret in text:
            text = text.replace(secret, "***REDACTED***")
    return text


# RabbitMQ AMQP URL parolasini regex ile maskeler:
#   amqp://user:password@host  →  amqp://user:***@host
# Genel safety net: kullanici register_secret unutsa bile parola log'a sizmasin.
_AMQP_PASSWORD_RE = re.compile(r"(amqp[s]?://[^:@\s/]+):([^@\s/]+)@", re.IGNORECASE)


def _scrub_amqp_passwords(text: str) -> str:
    if not text or "amqp" not in text.lower():
        return text
    return _AMQP_PASSWORD_RE.sub(r"\1:***@", text)


class _RedactionFilter(logging.Filter):
    """Tum log record'lardaki secret'leri redact eder.

    Hem `record.msg` hem `record.args` islenir; record.getMessage() her ikisini
    de kullanir. Exception text de redact edilir.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Mesaj: % formatlama oncesi
            if isinstance(record.msg, str):
                record.msg = _scrub_amqp_passwords(_scrub_message(record.msg))
            # Args (tuple veya dict)
            if record.args:
                if isinstance(record.args, tuple):
                    record.args = tuple(
                        _scrub_amqp_passwords(_scrub_message(a)) if isinstance(a, str) else a
                        for a in record.args
                    )
                elif isinstance(record.args, dict):
                    record.args = {
                        k: (_scrub_amqp_passwords(_scrub_message(v)) if isinstance(v, str) else v)
                        for k, v in record.args.items()
                    }
        except Exception:  # noqa: BLE001 — filter asla crash etmemeli
            pass
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        # Bir kere daha redact (bazi exception path'lerde args zaten consume edilmis olabilir)
        message = _scrub_amqp_passwords(_scrub_message(message))
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": message,
        }
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            payload["exc"] = _scrub_amqp_passwords(_scrub_message(exc_text))
        for key, value in record.__dict__.items():
            if key.startswith("ctx_"):
                payload[key[4:]] = (
                    _scrub_amqp_passwords(_scrub_message(value))
                    if isinstance(value, str)
                    else value
                )
        return json.dumps(payload, ensure_ascii=False)


class _TextFormatter(logging.Formatter):
    """Default text formatter + final redaction safety net."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        return _scrub_amqp_passwords(_scrub_message(text))


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Root logger'i idempotent bicimde yapilandirir.

    Birden fazla cagri guvenlidir (handler cogaltilmaz).

    Onemli: Bu noktadan SONRA register_secret() cagirilmasi onerilir; cunku
    filter aktif olduktan sonra eklenen secret'lar bir sonraki log'dan itibaren
    geçerli olur. Boot sirasinda ilk cagri configure_logging, sonra
    register_secret(token) ve register_secret(rabbitmq_url) yapilir.
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
            _TextFormatter(
                fmt="%(asctime)s %(levelname)-5s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    # Filter'i hem handler hem root'a ekle — handler'a eklemek formatter'dan
    # once cagrilir ki args vs.'da redaction olabilsin.
    redaction_filter = _RedactionFilter()
    handler.addFilter(redaction_filter)
    root.addHandler(handler)
    # AMQP baglanti ayrintilari: genelde sadece dnp3_gateway loglari yeterlidir
    logging.getLogger("pika").setLevel(logging.WARNING)
