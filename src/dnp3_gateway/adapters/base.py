"""Telemetri adapter'lari icin sozlesme."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from dnp3_gateway.backend import DeviceConfig, SignalConfig


@dataclass(frozen=True)
class SignalReading:
    """Tek bir sinyalin okunmus halini temsil eder.

    `raw_value`     : cihazdan gelen olceklendirilmemis ham deger (numeric tipler)
    `scaled_value`  : scale/offset uygulandiktan sonraki gercek deger (yayinlanir)
    `value_string`  : data_type='string' icin metin icerik (None = bilinmiyor)
                      Frontend numeric value yerine bunu gosterir.
    `quality`       : good | offline | invalid | comm_lost | restart | no_change
                      no_change: Event-driven okumada bu sinyal bu cycle'da
                      degisen event vermedi; cached deger gecerli, poller bunu
                      yayinlamaz (delta-only publish).
    """

    signal_key: str
    source: str
    data_type: str
    raw_value: float
    scaled_value: float
    quality: str = "good"
    value_string: str | None = None


class TelemetryReader(ABC):
    """Cihaz -> (sinyal listesi) okumasini sarmallayan adapter arayuzu."""

    @abstractmethod
    def read_device(
        self,
        *,
        device: DeviceConfig,
        signals: list[SignalConfig],
    ) -> list[SignalReading]:
        """Verilen cihazdan tum `signals` listesini okur.

        Implementasyon sirasinda hata olursa ya okuma basarisiz sinyaller
        quality='offline' / 'invalid' olarak donebilir ya da exception raise
        edilebilir. Exception uygulama katmaninda tek cihaz bazinda try/except
        ile loglanir, dongu durmaz.
        """

    def close(self) -> None:
        """Kaynak temizleme; varsayilanda no-op."""
