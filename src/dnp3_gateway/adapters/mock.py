"""Mock telemetri okuyucu.

Gercek DNP3 cihazi olmadan gateway'in baski testleri, tag-engine ile integrasyon
dogrulamasi ve frontend gelistirme icin kullanilabilir. Ureten degerler
Horstmann SN 2.0 sinyallerine gore mantikli araliklarda kalir.
"""

from __future__ import annotations

import random

from dnp3_gateway.adapters.base import SignalReading, TelemetryReader
from dnp3_gateway.backend import DeviceConfig, SignalConfig


class MockTelemetryReader(TelemetryReader):
    def __init__(self, *, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def read_device(
        self,
        *,
        device: DeviceConfig,
        signals: list[SignalConfig],
    ) -> list[SignalReading]:
        _ = device
        return [self._generate(signal) for signal in signals]

    # ------------------------------------------------------------------ impl
    def _generate(self, signal: SignalConfig) -> SignalReading:
        raw, quality = self._mock_value_for(signal)
        scaled = raw * signal.scale + signal.offset
        # data_type=string ise mock metin uret (cihaz seri no, firmware vb.)
        value_string: str | None = None
        if signal.data_type == "string":
            value_string = self._mock_string_for(signal)
        return SignalReading(
            signal_key=signal.key,
            source=signal.source,
            data_type=signal.data_type,
            raw_value=raw,
            scaled_value=round(scaled, 4),
            quality=quality,
            value_string=value_string,
        )

    def _mock_string_for(self, signal: SignalConfig) -> str:
        """Sinyal anahtarina gore makul bir mock metin uret. Frontend'de
        DNP3 G110 (Octet String) sinyallerin canli akmasini test etmek icin."""
        key = signal.key.lower()
        if "serial" in key:
            return f"SN-{self._rng.randint(100000, 999999)}"
        if "firmware" in key or "fw_version" in key:
            return f"v{self._rng.randint(1, 4)}.{self._rng.randint(0, 9)}.{self._rng.randint(0, 9)}"
        if "hardware" in key or "hw_version" in key:
            return f"hw-rev-{self._rng.choice(['A', 'B', 'C'])}{self._rng.randint(1, 5)}"
        if "model" in key or "device_type" in key:
            return self._rng.choice(["SN2-Master", "SN2-Sat", "SmartNav-2.0"])
        if "manufacturer" in key or "vendor" in key:
            return "Horstmann"
        if "location" in key or "site" in key:
            return self._rng.choice(["Pasinler-1", "Sarikamis-2", "Karakurt-3"])
        if "name" in key or "label" in key:
            return f"NODE-{self._rng.randint(1, 250):03d}"
        # Fallback - generic mock string
        return f"MOCK-{self._rng.randint(1000, 9999)}"

    def _mock_value_for(self, signal: SignalConfig) -> tuple[float, str]:
        key = signal.key.lower()
        data_type = signal.data_type

        if data_type in {"binary", "binary_output"}:
            return (1.0 if self._rng.random() < 0.04 else 0.0), "good"
        if data_type == "counter":
            return float(self._rng.randint(0, 50)), "good"
        if data_type == "string":
            return 0.0, "good"

        # analog / analog_output - Horstmann SN2 gergin araliklari
        if "actual_current" in key or "average_current" in key:
            return self._rng.uniform(0, 1500), "good"
        if "fault_current" in key:
            return self._rng.uniform(0, 8000), "good"
        if "min_current" in key or "minimum_current" in key:
            return self._rng.uniform(0, 200), "good"
        if "max_current" in key or "maximum_current" in key:
            return self._rng.uniform(500, 2500), "good"
        if "trip_level" in key or "trip_current" in key:
            return self._rng.uniform(400, 800), "good"
        if "last_good_known_current" in key:
            return self._rng.uniform(50, 1200), "good"
        if "fault_duration" in key:
            return self._rng.uniform(30, 400), "good"
        if any(k in key for k in ("actual_voltage", "minimum_voltage", "maximum_voltage", "nominal_voltage")):
            return self._rng.uniform(10000, 11500), "good"
        if "battery_voltage" in key:
            return self._rng.uniform(320, 420), "good"
        if "conductor_temperature" in key:
            return self._rng.uniform(2000, 8500), "good"
        if "device_temperature" in key:
            return self._rng.uniform(-500, 4500), "good"
        if "phase_angle" in key:
            return self._rng.uniform(-1800, 1800), "good"
        if "pitch_angle" in key:
            return self._rng.uniform(-4500, 4500), "good"
        if "modem_rssi" in key or "rssi_satellite" in key:
            return self._rng.uniform(-120, -60), "good"
        if "latitude" in key or "longitude" in key:
            return self._rng.uniform(0, 60), "good"
        if "reporting_period" in key:
            return 15.0, "good"
        if "test_point_level" in key:
            return self._rng.uniform(0, 100), "good"
        if "instantaneous_factor" in key:
            return self._rng.uniform(1, 10), "good"

        return self._rng.uniform(0, 100), "good"
