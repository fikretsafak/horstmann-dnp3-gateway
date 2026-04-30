from __future__ import annotations

import pytest

from dnp3_gateway.auth import resolve_instance_id
from dnp3_gateway.auth.identity import ensure_credentials_allowed
from dnp3_gateway.config import Settings


def test_resolve_instance_id_uses_env_when_set(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("GATEWAY_INSTANCE_ID", "fixed-id-1")
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        gateway_code="GW-001",
        gateway_instance_id="fixed-id-1",
        gateway_state_dir=str(tmp_path / "st"),
    )
    assert resolve_instance_id(settings=s) == "fixed-id-1"


def test_resolve_instance_id_persists_to_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("GATEWAY_INSTANCE_ID", raising=False)
    state_dir = tmp_path / "st"
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        gateway_code="GW-A",
        gateway_instance_id="",
        gateway_state_dir=str(state_dir),
    )
    a = resolve_instance_id(settings=s)
    b = resolve_instance_id(settings=s)
    assert a == b
    assert len(a) == 36  # uuid4 string
    assert any(state_dir.glob("instance_*.id"))


def test_production_rejects_placeholder_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("GATEWAY_TOKEN", "gw-default-token")
    monkeypatch.setenv("GATEWAY_CODE", "GW-001")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(SystemExit):
        ensure_credentials_allowed(s)


def test_production_requires_min_length(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("GATEWAY_TOKEN", "short")
    monkeypatch.setenv("GATEWAY_CODE", "GW-001")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(SystemExit):
        ensure_credentials_allowed(s)
