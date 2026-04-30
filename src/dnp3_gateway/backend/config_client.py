"""Backend `/gateways/{code}/config` endpoint'i icin kucuk HTTP client.

Horstmann Smart Logger cati backend'i her gateway icin kendi cihaz listesini +
standart sinyal katalogunu donmekle yukumludur. Bu modulun gorevi:

  - Endpoint'i periyodik olarak cagirmak
  - JSON payload'unu tipli dataclass'lara (DeviceConfig / SignalConfig /
    GatewayConfig) cevirmek
  - Ag/Oturum/Token hatalarini `GatewayConfigError` ile raise etmek

Backend'in `config_version` hash'i ayni kaldigi surece upstream'e gereksiz
refresh yapilmaz. Degistiginde `GatewayState.update()` true doner ve log'a
"configuration changed" satiri yazilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from dnp3_gateway.auth import GatewayIdentity, build_config_request_headers


@dataclass(frozen=True)
class DeviceConfig:
    """Tek bir Horstmann SN 2.0 cihazinin baglanti parametreleri.

    `dnp3_tcp_port` None ise gateway `.env` `DNP3_TCP_PORT` (varsayilan) kullanilir;
    aksi halde cihaz bazli TCP port (backend/frontend cihaz kaydi).

    `master_address` None ise gateway `.env` `DNP3_LOCAL_ADDRESS` (varsayilan 1)
    kullanilir; aksi halde frontend'de cihaz basina set edilen master/local addr
    (DNP3 link layer LocalAddr) kullanilir. Saha cihazi bu adresi bekler.

    `ip_endpoint_type`:
      - "listening" (default): cihaz dinler, gateway TCP client olarak baglanir
      - "initiating": cihaz master'a outbound baglanir (4G/SIM kart sahasi);
        gateway bu cihaz icin `master_ip_port` portunda TCP server acar
    """

    code: str
    name: str
    ip_address: str
    dnp3_address: int = 1
    dnp3_tcp_port: int | None = None
    master_address: int | None = None
    ip_endpoint_type: str = "listening"
    master_ip_port: int | None = None
    poll_interval_sec: int = 5
    timeout_ms: int = 3000
    retry_count: int = 2
    signal_profile: str = "horstmann_sn2_fixed"


@dataclass(frozen=True)
class SignalConfig:
    """Sinyal kataloğundan gelen tek satir.

    DNP3 adresleme:
      - object_group 1  : binary input
      - object_group 10 : binary output (komut)
      - object_group 20 : counter
      - object_group 30 : analog input
      - object_group 40 : analog output
      - object_group 110: string (Horstmann'da seri no, firmware vb.)
    """

    key: str
    label: str
    unit: str | None
    source: str  # master | sat01 | sat02
    dnp3_class: str
    data_type: str  # analog | binary | counter | analog_output | binary_output | string
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
    devices: list[DeviceConfig] = field(default_factory=list)
    signals: list[SignalConfig] = field(default_factory=list)


class GatewayConfigError(RuntimeError):
    """Backend API config endpoint'inden gecerli bir yanit alinamadi."""


def _parse_optional_dnp3_tcp_port(item: dict[str, Any]) -> int | None:
    """Backend alan adlari: dnp3_tcp_port | dnp3_port | tcp_port. Gecerli: 1-65535."""
    for key in ("dnp3_tcp_port", "dnp3_port", "tcp_port"):
        if key not in item or item[key] is None or item[key] == "":
            continue
        try:
            p = int(item[key])
        except (TypeError, ValueError):
            continue
        if 1 <= p <= 65535:
            return p
    return None


def _parse_optional_master_address(item: dict[str, Any]) -> int | None:
    """Backend alan adlari: master_address | dnp3_master_address | local_address."""
    for key in ("master_address", "dnp3_master_address", "local_address"):
        if key not in item or item[key] is None or item[key] == "":
            continue
        try:
            a = int(item[key])
        except (TypeError, ValueError):
            continue
        if 0 <= a <= 65519:  # DNP3 link addr range (broadcast addrs hariç)
            return a
    return None


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}


def _rewrite_loopback_ip(ip: str, *, enabled: bool) -> str:
    """Container icinde loopback IP host.docker.internal'a cevirilir.

    Frontend'de kullanici cihazi "127.0.0.1" olarak ayarladiysa (cati yazilim
    ve gateway ayni makinada) ve gateway Docker'da calisiyorsa bu IP
    container'in kendisini gosterir. host.docker.internal Linux Docker 20.10+
    ve Docker Desktop tarafindan host'un IPv4 adresine cevrilir; compose
    template'inde bu mapping zaten "extra_hosts: host-gateway" ile garanti.
    """

    if not enabled:
        return ip
    h = (ip or "").strip().lower()
    if h in _LOOPBACK_HOSTS:
        return "host.docker.internal"
    return ip


class BackendConfigClient:
    """HTTP client: `X-Gateway-Token` + tanimli kimlik basliklari ile auth."""

    def __init__(
        self,
        *,
        base_url: str,
        identity: GatewayIdentity,
        timeout_sec: int = 5,
        session: requests.Session | None = None,
        verify: bool | str = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.identity = identity
        self.gateway_code = identity.gateway_code
        self.timeout_sec = timeout_sec
        self._session = session or requests.Session()
        if session is None:
            self._session.verify = verify  # type: ignore[assignment]

    def fetch_config(self) -> GatewayConfig:
        url = f"{self.base_url}/gateways/{self.gateway_code}/config"
        headers = build_config_request_headers(self.identity)
        try:
            response = self._session.get(url, headers=headers, timeout=self.timeout_sec)
        except requests.RequestException as exc:
            raise GatewayConfigError(f"config request failed: {exc}") from exc

        if response.status_code != 200:
            raise GatewayConfigError(
                f"config request returned {response.status_code}: {response.text[:200]}"
            )

        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise GatewayConfigError(f"config response is not json: {exc}") from exc

        return _parse_gateway_config(data, default_gateway_code=self.gateway_code)


def _parse_gateway_config(data: dict[str, Any], *, default_gateway_code: str) -> GatewayConfig:
    """Bos/bozuk alanlari varsayilanlarla doldurarak GatewayConfig ureten helper."""

    # Env flag (default True): loopback device IP'yi container icinde
    # host.docker.internal'a cevir. Tipik kurulum (cati yazilim + simulator
    # ayni Windows host'unda) icin gerekli; ozel saha kurulumlarinda
    # kapatilabilir (REWRITE_LOOPBACK_TO_HOST=false).
    import os as _os

    rewrite = (_os.environ.get("REWRITE_LOOPBACK_TO_HOST", "true").strip().lower()
               not in ("0", "false", "no", "off"))

    devices_raw = data.get("devices") or []
    devices = [
        DeviceConfig(
            code=str(item["code"]),
            name=str(item.get("name") or item["code"]),
            ip_address=_rewrite_loopback_ip(
                str(item.get("ip_address") or ""), enabled=rewrite
            ),
            dnp3_address=int(item.get("dnp3_address", 1) or 1),
            dnp3_tcp_port=_parse_optional_dnp3_tcp_port(item),
            master_address=_parse_optional_master_address(item),
            ip_endpoint_type=(
                str(item.get("ip_endpoint_type") or "listening").strip().lower()
                if str(item.get("ip_endpoint_type") or "").strip().lower() in ("initiating", "listening")
                else "listening"
            ),
            master_ip_port=(
                int(item["master_ip_port"])
                if item.get("master_ip_port") not in (None, "", 0) and 1 <= int(item["master_ip_port"]) <= 65535
                else None
            ),
            poll_interval_sec=int(item.get("poll_interval_sec", 5) or 5),
            timeout_ms=int(item.get("timeout_ms", 3000) or 3000),
            retry_count=int(item.get("retry_count", 2) or 2),
            signal_profile=str(item.get("signal_profile") or "horstmann_sn2_fixed"),
        )
        for item in devices_raw
        if item.get("code")
    ]

    signals_raw = data.get("signals") or []
    signals = [
        SignalConfig(
            key=str(item["key"]),
            label=str(item.get("label") or item["key"]),
            unit=(str(item["unit"]) if item.get("unit") else None),
            source=str(item.get("source") or "master"),
            dnp3_class=str(item.get("dnp3_class") or "Class 1"),
            data_type=str(item.get("data_type") or "analog"),
            dnp3_object_group=int(item.get("dnp3_object_group", 30) or 30),
            dnp3_index=int(item.get("dnp3_index", 0) or 0),
            scale=float(item.get("scale", 1.0) or 1.0),
            offset=float(item.get("offset", 0.0) or 0.0),
            supports_alarm=bool(item.get("supports_alarm", False)),
        )
        for item in signals_raw
        if item.get("key")
    ]

    return GatewayConfig(
        gateway_code=str(data.get("gateway_code") or default_gateway_code),
        gateway_name=str(data.get("gateway_name") or ""),
        batch_interval_sec=int(data.get("batch_interval_sec", 5) or 5),
        max_devices=int(data.get("max_devices", 200) or 200),
        is_active=bool(data.get("is_active", True)),
        config_version=str(data.get("config_version") or ""),
        devices=devices,
        signals=signals,
    )
