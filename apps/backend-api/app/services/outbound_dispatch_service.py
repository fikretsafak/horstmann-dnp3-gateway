import json
import time
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbound_target import OutboundTarget
from app.services.event_service import record_event

MAX_RETRY = 3
BASE_BACKOFF_SECONDS = 0.7

try:
    import paho.mqtt.publish as mqtt_publish
except ImportError:  # pragma: no cover
    mqtt_publish = None


def dispatch_event(db: Session, *, event_kind: str, payload: dict) -> None:
    stmt = select(OutboundTarget).where(OutboundTarget.is_active.is_(True))
    targets = list(db.scalars(stmt).all())
    for target in targets:
        if target.event_filter not in {"all", event_kind}:
            continue
        _dispatch_with_retry(db=db, target=target, event_kind=event_kind, payload=payload)


def _dispatch_with_retry(db: Session, *, target: OutboundTarget, event_kind: str, payload: dict) -> None:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            if target.protocol == "rest":
                _send_rest(target, payload)
            elif target.protocol == "mqtt":
                _send_mqtt(target, payload)
            else:
                raise ValueError(f"Unsupported outbound protocol: {target.protocol}")
            record_event(
                db,
                category="outbound",
                event_type="outbound_delivered",
                severity="info",
                message=f"{target.name} hedefine {event_kind} eventi gönderildi",
                metadata={"target": target.name, "protocol": target.protocol, "attempt": attempt},
            )
            return
        except Exception as ex:
            last_error = ex
            if attempt < MAX_RETRY:
                wait_seconds = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                record_event(
                    db,
                    category="outbound",
                    event_type="outbound_retry_scheduled",
                    severity="warning",
                    message=f"{target.name} için retry planlandı (deneme {attempt}/{MAX_RETRY})",
                    metadata={
                        "target": target.name,
                        "protocol": target.protocol,
                        "attempt": attempt,
                        "backoff_seconds": wait_seconds,
                        "error": str(ex),
                    },
                )
                time.sleep(wait_seconds)

    record_event(
        db,
        category="outbound",
        event_type="outbound_dead_letter",
        severity="error",
        message=f"{target.name} hedefine gönderim dead-letter kuyruğuna düştü",
        metadata={
            "target": target.name,
            "protocol": target.protocol,
            "max_retry": MAX_RETRY,
            "error": str(last_error) if last_error else "unknown",
            "payload": payload,
        },
    )


def _send_rest(target: OutboundTarget, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if target.auth_header and target.auth_token:
        headers[target.auth_header] = target.auth_token
    req = urllib.request.Request(target.endpoint, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=8):
        pass


def _send_mqtt(target: OutboundTarget, payload: dict) -> None:
    if mqtt_publish is None:
        raise RuntimeError("MQTT publish için paho-mqtt kurulu değil.")
    if not target.topic:
        raise ValueError("MQTT target için topic zorunludur.")
    mqtt_publish.single(
        target.topic,
        payload=json.dumps(payload, ensure_ascii=False),
        hostname=target.endpoint,
        qos=target.qos,
        retain=target.retain,
    )
