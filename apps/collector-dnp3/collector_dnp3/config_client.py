from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class DeviceConfig:
    code: str
    name: str
    ip_address: str
    dnp3_address: int
    poll_interval_sec: int
    timeout_ms: int
    retry_count: int
    signal_profile: str


@dataclass(frozen=True)
class SignalConfig:
    key: str
    label: str
    unit: str | None
    source: str  # "master" | "sat01" | "sat02" - Horstmann SN2 ünite ayrımı
    dnp3_class: str
    data_type: str
    dnp3_object_group: int
    dnp3_index: int
    scale: float
    offset: float
    supports_alarm: bool


@dataclass(frozen=True)
class GatewayConfig:
    gateway_code: str
    gateway_name: str
    batch_interval_sec: int
    max_devices: int
    is_active: bool
    config_version: str
    devices: list[DeviceConfig]
    signals: list[SignalConfig]


class GatewayConfigError(RuntimeError):
    """Backend API config endpoint'inden geçerli bir yanıt alınamadı."""


class BackendConfigClient:
    """Backend API `/gateways/{code}/config` endpoint'i için küçük istemci.

    Gateway, kendi kimliği ile backend'e sorup cihaz listesini ve operasyonel
    parametrelerini çeker. Token hatalı ya da gateway pasif ise istek başarısız olur.
    """

    def __init__(self, *, base_url: str, gateway_code: str, gateway_token: str, timeout_sec: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.gateway_code = gateway_code
        self.gateway_token = gateway_token
        self.timeout_sec = timeout_sec

    def fetch_config(self) -> GatewayConfig:
        url = f"{self.base_url}/gateways/{self.gateway_code}/config"
        headers = {"X-Gateway-Token": self.gateway_token}
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout_sec)
        except requests.RequestException as exc:
            raise GatewayConfigError(f"config request failed: {exc}") from exc

        if response.status_code != 200:
            raise GatewayConfigError(
                f"config request returned {response.status_code}: {response.text[:200]}"
            )

        data: dict[str, Any] = response.json()
        devices_raw = data.get("devices", []) or []
        devices = [
            DeviceConfig(
                code=item["code"],
                name=item["name"],
                ip_address=item["ip_address"],
                dnp3_address=int(item.get("dnp3_address", 1)),
                poll_interval_sec=int(item.get("poll_interval_sec", 5)),
                timeout_ms=int(item.get("timeout_ms", 3000)),
                retry_count=int(item.get("retry_count", 2)),
                signal_profile=item.get("signal_profile") or "default",
            )
            for item in devices_raw
        ]
        signals_raw = data.get("signals", []) or []
        signals = [
            SignalConfig(
                key=item["key"],
                label=item.get("label", item["key"]),
                unit=item.get("unit"),
                source=item.get("source") or "master",
                dnp3_class=item.get("dnp3_class") or "Class 1",
                data_type=item.get("data_type") or "analog",
                dnp3_object_group=int(item.get("dnp3_object_group", 30)),
                dnp3_index=int(item.get("dnp3_index", 0)),
                scale=float(item.get("scale", 1.0)),
                offset=float(item.get("offset", 0.0)),
                supports_alarm=bool(item.get("supports_alarm", False)),
            )
            for item in signals_raw
        ]
        return GatewayConfig(
            gateway_code=data.get("gateway_code", self.gateway_code),
            gateway_name=data.get("gateway_name", ""),
            batch_interval_sec=int(data.get("batch_interval_sec", 5)),
            max_devices=int(data.get("max_devices", 200)),
            is_active=bool(data.get("is_active", True)),
            config_version=str(data.get("config_version", "")),
            devices=devices,
            signals=signals,
        )
