from __future__ import annotations

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


def test_dnp3_mode_flag(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GATEWAY_MODE", "dnp3")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.is_dnp3_mode is True
    assert s.is_mock_mode is False
