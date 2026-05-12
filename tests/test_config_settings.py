from __future__ import annotations

import pytest

from dnp3_gateway.config import Settings


def test_settings_defaults_are_sensible() -> None:
    # Test icin disk'teki .env'yi kullanma
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.gateway_mode == "mock"
    assert s.rabbitmq_routing_key == "telemetry.raw_received"
    assert s.rabbitmq_exchange == "hsl.events"
    assert s.worker_health_port == 8020
    assert s.is_mock_mode is True
    assert s.is_dnp3_mode is False
    # Default FALSE: token konsola yazilmasin (logging aggregator'larda leak
    # olmasin). Operator istege bagli SHOW_GATEWAY_TOKEN_ON_START=true ile
    # gecici acabilir; production'da validator zaten bunu engeller.
    assert s.show_gateway_token_on_start is False
    # GATEWAY_REFRESH_TOKEN default bos; main.py /refresh-all icin
    # GATEWAY_TOKEN'a fallback eder ve uyari log atar.
    assert s.gateway_refresh_token == ""
    # Default FALSE — public host'a clear-text HTTP/nats:// validator
    # tarafindan reddedilir; bilincli opt-out gerekir.
    assert s.gateway_insecure_allow_plaintext is False


def test_dnp3_mode_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_MODE", "dnp3")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.is_dnp3_mode is True
    assert s.is_mock_mode is False


# ---- Production validator: private vs. public host esnemesi ---------------
# Validator artik host bazli karar veriyor:
#   - Public host (orn. 77.83.37.44, example.com) -> https://+tls:// zorunlu
#   - Private host (10.x, 192.168.x, 127.x, *.local, localhost) -> http://+nats:// ok
#   - GATEWAY_INSECURE_ALLOW_PLAINTEXT=true -> public host'a da clear-text izin


def _strong_token() -> str:
    return "x" * 40  # >=32 char prod min length


def test_prod_allows_http_to_private_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Internal deploy: backend 192.168.x'te, gateway prod ortaminda."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("GATEWAY_TOKEN", _strong_token())
    monkeypatch.setenv("BACKEND_API_URL", "http://192.168.1.10:8000/api/v1")
    monkeypatch.setenv("NATS_URL", "nats://192.168.1.10:4222")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.backend_api_url.startswith("http://")
    assert s.nats_url.startswith("nats://")


def test_prod_allows_http_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same-host deploy: backend container 127.0.0.1'de."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("GATEWAY_TOKEN", _strong_token())
    monkeypatch.setenv("BACKEND_API_URL", "http://127.0.0.1:8000/api/v1")
    monkeypatch.setenv("NATS_URL", "nats://localhost:4222")
    Settings(_env_file=None)  # type: ignore[call-arg]  # raise etmemeli


def test_prod_rejects_http_to_public_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Saha hatasi: public IP'ye clear-text HTTP — token MITM riski."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("GATEWAY_TOKEN", _strong_token())
    monkeypatch.setenv("BACKEND_API_URL", "http://77.83.37.44:8000/api/v1")
    monkeypatch.setenv("NATS_URL", "nats://77.83.37.44:4222")
    with pytest.raises(ValueError, match="public host"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_prod_rejects_nats_clear_text_to_public_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend HTTPS, ama NATS hala public clear-text — yine reddedilmeli."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("GATEWAY_TOKEN", _strong_token())
    monkeypatch.setenv("BACKEND_API_URL", "https://api.example.com/api/v1")
    monkeypatch.setenv("NATS_URL", "nats://nats.example.com:4222")
    with pytest.raises(ValueError, match="public NATS host"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_prod_allows_public_http_when_insecure_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator bilincli opt-out: TLS henuz kurulamadi, public IP'de calisiyor."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("GATEWAY_TOKEN", _strong_token())
    monkeypatch.setenv("BACKEND_API_URL", "http://77.83.37.44:8000/api/v1")
    monkeypatch.setenv("NATS_URL", "nats://77.83.37.44:4222")
    monkeypatch.setenv("GATEWAY_INSECURE_ALLOW_PLAINTEXT", "true")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.gateway_insecure_allow_plaintext is True


def test_prod_accepts_https_public(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hedef deploy: backend HTTPS, NATS TLS — temiz prod konfigurasyonu."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("GATEWAY_TOKEN", _strong_token())
    monkeypatch.setenv("BACKEND_API_URL", "https://hsl.formelektrik.com/api/v1")
    monkeypatch.setenv("NATS_URL", "tls://nats.formelektrik.com:4222")
    Settings(_env_file=None)  # type: ignore[call-arg]
