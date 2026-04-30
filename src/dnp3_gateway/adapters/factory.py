"""Gateway mode'una gore uygun adapter'i ureten kucuk factory."""

from __future__ import annotations

import logging

from dnp3_gateway.adapters.base import TelemetryReader
from dnp3_gateway.adapters.mock import MockTelemetryReader
from dnp3_gateway.config import Settings

logger = logging.getLogger(__name__)


def build_adapter(settings: Settings) -> TelemetryReader:
    mode = settings.gateway_mode.strip().lower()
    if mode == "mock":
        logger.info("adapter_selected mode=mock")
        return MockTelemetryReader()

    if mode != "dnp3":
        raise ValueError(f"desteklenmeyen gateway_mode={settings.gateway_mode}")

    library = (settings.dnp3_library or "yadnp3").strip().lower()
    if library in ("yadnp3", "opendnp3"):
        from dnp3_gateway.adapters.dnp3_yadnp3_master import Yadnp3TelemetryReader

        logger.info(
            "adapter_selected mode=dnp3 library=yadnp3 (OpenDNP3) local_addr=%s default_tcp=%s "
            "scan=%ss baseline=%ss",
            settings.dnp3_local_address,
            settings.dnp3_tcp_port,
            settings.default_poll_interval_sec,
            settings.dnp3_event_baseline_interval_sec,
        )
        return Yadnp3TelemetryReader(
            local_address=settings.dnp3_local_address,
            default_dnp3_tcp_port=settings.dnp3_tcp_port,
            scan_interval_sec=settings.default_poll_interval_sec,
            baseline_interval_sec=settings.dnp3_event_baseline_interval_sec,
        )

    if library == "dnp3py":
        # Legacy: nfm-dnp3 (saf python). Group 110 yok, OpenDNP3 outstation
        # ile tutarsiz davranis. Sadece ozel durumlar icin.
        from dnp3_gateway.adapters.dnp3_master import Dnp3TelemetryReader

        logger.warning(
            "adapter_selected mode=dnp3 library=dnp3py (LEGACY, Group 110 yok). "
            "Onerilen: DNP3_LIBRARY=yadnp3"
        )
        return Dnp3TelemetryReader(
            local_address=settings.dnp3_local_address,
            default_dnp3_tcp_port=settings.dnp3_tcp_port,
            response_timeout_sec=settings.dnp3_response_timeout_sec,
            read_strategy=settings.dnp3_read_strategy,
            direct_max_points_per_read=settings.dnp3_direct_max_points_per_read,
            direct_sparse_ratio=settings.dnp3_direct_sparse_ratio,
            confirm_required=settings.dnp3_confirm_required,
            link_reset_on_connect=settings.dnp3_link_reset_on_connect,
            disable_unsolicited_on_connect=settings.dnp3_disable_unsolicited_on_connect,
            unsolicited_class_mask=settings.dnp3_unsolicited_class_mask,
            event_baseline_interval_sec=settings.dnp3_event_baseline_interval_sec,
            log_raw_frames=settings.dnp3_log_raw_frames,
        )

    raise ValueError(
        f"desteklenmeyen DNP3_LIBRARY={settings.dnp3_library!r} (yadnp3 | dnp3py)"
    )
