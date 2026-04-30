"""Telemetri okuma adapter'larinin disari actigi arayuz.

Adapter, gateway'in bir cihaza baglanip o cihazdan tum sinyalleri okuma
gorevini usthenir. Sinyal katalogundaki her kayit icin `SignalReading` uretir.

Mock ve gercek DNP3 adapter'i ayni arayuzu implement eder; boylece poller/main
kodu protokolden soyutlanir.
"""

from dnp3_gateway.adapters.base import SignalReading, TelemetryReader
from dnp3_gateway.adapters.factory import build_adapter
from dnp3_gateway.adapters.mock import MockTelemetryReader

__all__ = [
    "SignalReading",
    "TelemetryReader",
    "MockTelemetryReader",
    "build_adapter",
]
