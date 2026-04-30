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
    assert s.show_gateway_token_on_start is True


def test_dnp3_mode_flag(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GATEWAY_MODE", "dnp3")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.is_dnp3_mode is True
    assert s.is_mock_mode is False
