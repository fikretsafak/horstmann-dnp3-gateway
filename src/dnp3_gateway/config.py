"""Gateway konfigurasyonu - environment degiskenleri + .env dosyasindan okunur."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tum gateway ayarlarini tek yerde toplayan pydantic modeli.

    Oncelik sirasi:
      1. process env degiskenleri
      2. `.env` dosyasi
      3. asagidaki varsayilanlar
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- Gateway kimligi -----------------------------------------------------
    gateway_code: str = Field(default="GW-001", description="Backend 'gateways.code' ile eslesen kimlik")
    gateway_token: str = Field(default="gw-default-token", description="Backend 'gateways.token' degeri")
    gateway_name: str = Field(default="Horstmann SN2 Gateway", description="Log/health icin insan-okur isim")

    # Ornek/destek: bos ise `GATEWAY_STATE_DIR` altinda kalici uuid dosyasina yazilir
    gateway_instance_id: str = Field(default="", description="Benzersiz proses ornek id (log/baglanti)")
    gateway_state_dir: str = Field(
        default=".gateway_state",
        description="instance_id dosyasinin tutulacagi dizin (coklu gateway icin ayri kod)",
    )

    # Gelistirme: development. Staging/production: token min uzunluk + placeholder yasak
    app_environment: str = Field(
        default="development",
        description="development | staging | production (kisa: dev, stg, prod)",
    )
    gateway_token_min_length_staging: int = Field(default=16, ge=8, le=256)
    gateway_token_min_length_production: int = Field(default=32, ge=16, le=256)

    # ----- Calisma modu --------------------------------------------------------
    gateway_mode: str = Field(default="mock", description="mock | dnp3")

    # DNP3 master kutuphane secimi:
    #   yadnp3 (varsayilan) = OpenDNP3 reference; full DNP3 standardi,
    #     Group 110 (Octet String) destekler, event-driven (AddClassScan), tum
    #     outstation'larla %100 uyumlu (cunku ayni outstation kutuphanesi).
    #   dnp3py = nfm-dnp3 saf python; daha hafif ama Group 110 yok ve OpenDNP3
    #     outstation'lar ile tutarsiz davranis (TCP RST, transport segment).
    dnp3_library: str = Field(
        default="yadnp3",
        description="DNP3 master kutuphanesi: yadnp3 (onerilen) | dnp3py (legacy)",
    )

    # ----- Backend API ---------------------------------------------------------
    backend_api_url: str = Field(default="http://127.0.0.1:8000/api/v1")
    backend_api_verify_ssl: bool = Field(default=True, description="False sadece dev/test (MITM riski)")
    backend_api_ca_path: str | None = Field(
        default=None,
        description="TLS icin ozel CA bundle yolu; bos = sistem varsayilani + verify_ssl",
    )
    config_refresh_sec: int = Field(default=30, ge=5, le=3600)
    config_timeout_sec: int = Field(default=5, ge=1, le=60)
    config_cache_max_age_hours: float = Field(
        default=24.0,
        ge=1.0,
        le=720.0,
        description=(
            "Disk'teki config cache'i kac saatten daha eski olunca 'stale' "
            "kabul edilir. Backend down kalsa bile gateway eski config ile "
            "polling'e devam eder, ancak /health endpoint'i 'cache_stale' "
            "raporlar. Operator backend baglantisini cozmesi icin alarm."
        ),
    )

    # ----- RabbitMQ ------------------------------------------------------------
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    rabbitmq_exchange: str = Field(default="hsl.events")
    rabbitmq_routing_key: str = Field(default="telemetry.raw_received")

    # ----- Health HTTP ---------------------------------------------------------
    worker_health_host: str = Field(default="127.0.0.1")
    worker_health_port: int = Field(
        default=8020,
        ge=0,
        le=65535,
        description=(
            "Health/metrics HTTP portu. 0 verilirse OS rastgele bos port atar; "
            "gercek port baslangictaki log'da ve /health icinde gosterilir. "
            "Ayni PC'de coklu gateway icin her birine ayri port verin."
        ),
    )

    # ----- Polling davranisi ---------------------------------------------------
    default_poll_interval_sec: int = Field(default=5, ge=1, le=3600)
    max_parallel_devices: int = Field(default=25, ge=1, le=500)
    # Tek bir cihaz okuma + publish icin maksimum sure (sn). Bu sureyi asarsa
    # cihaz "timeout" kabul edilir, mark_read cagirilir, diger cihazlar
    # etkilenmez. 100+ cihazda 1-2 hangat olan cihaz tum cycle'i bloke etmesin.
    device_poll_timeout_sec: float = Field(
        default=30.0,
        ge=1.0,
        le=600.0,
        description="Tek cihaz icin poll+publish maksimum sure (sn)",
    )
    # Tum cycle (paralel due_devices) icin global timeout. Uygulama default
    # device_timeout * sqrt(devices) ya da bu sabit; hangisi buyuk.
    cycle_timeout_sec: float = Field(
        default=120.0,
        ge=10.0,
        le=3600.0,
        description="Bir poll cycle'in (paralel) maksimum suresi (sn)",
    )
    # Container icinde calisirken cihaz IP'si "127.0.0.1" / "localhost" /
    # "0.0.0.0" olarak gelmisse host'a (host.docker.internal) cevir. Cati
    # yazilim + simulator + gateway ayni Windows host'unda calisirken bu
    # gerekli — aksi halde container kendisine baglanmaya calisir.
    rewrite_loopback_to_host: bool = Field(
        default=True,
        description="Device IP loopback ise host.docker.internal'a cevirilsin mi",
    )

    # ----- Outbox / messaging dayaniklilik -----------------------------------
    outbox_max_pending: int = Field(
        default=500_000,
        ge=1_000,
        le=10_000_000,
        description=(
            "Outbox doluluk limiti. Ulasilirsa publisher disk-full circuit "
            "breaker tetikler ve poll cycle'i durdurur (sessiz veri kaybi yerine "
            "kontrollu duraklatma). Saniyede ortalama 200 mesaj ile ~40 dakika "
            "broker outage karsilar."
        ),
    )
    outbox_max_retries: int = Field(
        default=100,
        ge=1,
        le=10_000,
        description=(
            "Bir mesaj kac kere yeniden gonderilmeye calisilirsa dead-letter "
            "tablosuna tasinir (poison message korumasi)."
        ),
    )
    outbox_retrier_min_backoff_sec: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="OutboxRetrier minimum backoff (broker dustugunde ilk bekleme)",
    )
    outbox_retrier_max_backoff_sec: float = Field(
        default=60.0,
        ge=1.0,
        le=600.0,
        description="OutboxRetrier maksimum backoff (broker uzun sure dustugunde cap)",
    )
    outbox_retrier_poll_interval_sec: float = Field(
        default=2.0,
        ge=0.5,
        le=60.0,
        description="OutboxRetrier saglikli durumda batch'ler arasi bekleme",
    )
    outbox_retrier_batch_size: int = Field(
        default=200,
        ge=1,
        le=2000,
        description="Outbox'tan tek seferde alinan mesaj sayisi",
    )

    # ----- DNP3 master parametreleri ------------------------------------------
    dnp3_local_address: int = Field(default=1, ge=0, le=65519)
    dnp3_tcp_port: int = Field(
        default=20000,
        ge=1,
        le=65535,
        description="Varsayilan DNP3 TCP port; cihaz API'de dnp3_tcp_port verirse o baskin",
    )
    dnp3_integrity_poll_min: int = Field(default=60, ge=1, le=86400)
    dnp3_response_timeout_sec: int = Field(
        default=15,
        ge=1,
        le=120,
        description="DNP3 yanit bekleme (s); tekil index okumalari coklu sinyalde toplam sureye eklenir",
    )
    dnp3_read_strategy: str = Field(
        default="event_driven",
        description=(
            "event_driven (varsayilan) = Class 1+2+3 event poll + periyodik Class 0 baseline "
            "(degisen noktalari yayinlar; 100+ cihaz icin onerilen) | "
            "direct = grup+index araligi (hafif, simulator uyumlu) | "
            "class0 = sadece statik (her cycle hepsini publish eder) | "
            "integrity = tum classlar (en kapsamli, en yorucu)."
        ),
    )
    dnp3_event_baseline_interval_sec: int = Field(
        default=60,
        ge=5,
        le=86400,
        description=(
            "event_driven mod: bu kadar saniyede bir Class 0 (tam baseline) tazelenir; "
            "arada Class 1/2/3 event poll yapilir. Drift toleransi olarak 30-300 sn idealdir."
        ),
    )
    dnp3_direct_max_points_per_read: int = Field(
        default=24,
        ge=1,
        le=250,
        description="Bir DNP3 READ'de en fazla kac nokta (0-123 gibi aralik cokluklarda parcalar)",
    )
    dnp3_direct_sparse_ratio: int = Field(
        default=4,
        ge=2,
        le=20,
        description="benzersizIndexSayisi*oran < min-max+1 ise 'seyrek' kabul, sadece o indexlere tekil okur",
    )
    dnp3_confirm_required: bool = Field(
        default=False,
        description="Data link onayli cerceve; OpenDNP3/Horstmann sim ile False genelde gerekir",
    )
    dnp3_link_reset_on_connect: bool = Field(
        default=True,
        description="TCP acildiktan sonra DNP3 Reset Link; bazi OpenDNP3 outstation'lar icin onerilir",
    )
    dnp3_disable_unsolicited_on_connect: bool = Field(
        default=False,
        description=(
            "Connect+Reset Link sonrasi DISABLE_UNSOLICITED gonderir. "
            "OpenDNP3 outstation (Horstmann SN2 + simulator) bu mesaja bazen TCP'yi "
            "kapatarak cevap verir; bu yuzden VARSAYILAN false. Empty-frame filter "
            "unsolicited frame'leri zaten yutuyor; gerekmiyorsa kapali kalsin."
        ),
    )
    dnp3_unsolicited_class_mask: int = Field(
        default=7,
        ge=0,
        le=7,
        description="Bitmask: 1=Class1, 2=Class2, 4=Class3 (varsayilan 7=hepsi)",
    )
    dnp3_log_raw_frames: bool = Field(
        default=False,
        description="nfm-dnp3 ham TX/RX cercevelerini loglar (sorun giderme; cok gurultulu)",
    )

    # ----- Logging -------------------------------------------------------------
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="text", description="text | json")
    # True: baslangicta konsola tam token yazilir (.env: SHOW_GATEWAY_TOKEN_ON_START=false maskeli).
    show_gateway_token_on_start: bool = Field(default=True)

    @property
    def is_mock_mode(self) -> bool:
        return self.gateway_mode.strip().lower() == "mock"

    @property
    def is_dnp3_mode(self) -> bool:
        return self.gateway_mode.strip().lower() == "dnp3"


settings = Settings()
