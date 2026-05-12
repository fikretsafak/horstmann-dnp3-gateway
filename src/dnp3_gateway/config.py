"""Gateway konfigurasyonu - environment degiskenleri + .env dosyasindan okunur."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
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
    gateway_refresh_token: str = Field(
        default="",
        description=(
            "POST /refresh-all icin ayri token (rol ayrimi). Bos birakilirsa "
            "endpoint devre disi kalir. GATEWAY_TOKEN'dan FARKLI olmali; ayni "
            "ise backend tokeni leak olunca tum gateway'leri uzaktan yorma "
            "(DoS) acilir."
        ),
    )
    gateway_name: str = Field(default="EnerjiOne DNP3 Gateway", description="Log/health icin insan-okur isim")

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

    # ----- NATS JetStream (PRIMARY — gateway'in tek telemetri yayinlama yolu) -
    # Gateway artik tum telemetriyi DIRECT JetStream'e basar. RabbitMQ telemetri
    # akisindan kaldirildi; sadece backend tarafindaki alarm.created akisi icin
    # RabbitMQ kullaniliyor — gateway onunla ilgilenmez.
    #
    # NATS down olunca: publish hatasi -> outbox'a yazilir -> retrier baglanti
    # gelince bosaltir. At-least-once garantisi outbox + Nats-Msg-Id broker-side
    # dedup'i ile saglanir.
    nats_url: str = Field(
        default="nats://localhost:4222",
        description=(
            "NATS JetStream server adresi (ZORUNLU). Compose icinden "
            "nats://nats:4222; ayri host'tan nats://<host>:4222."
        ),
    )
    nats_subject_prefix: str = Field(
        default="e1.telemetry.raw",
        description=(
            "JetStream subject prefix. Konkre subject `<prefix>.<gateway_code>` "
            "seklinde olusturulur (orn. e1.telemetry.raw.GW-001). Backend "
            "stream TELEMETRY_RAW bu prefix'i `e1.telemetry.raw.>` wildcard "
            "ile yakalar."
        ),
    )
    nats_connect_timeout_sec: int = Field(
        default=5,
        ge=1,
        le=60,
        description=(
            "NATS connect timeout. Kisa tutun ki gateway startup'i NATS yokken "
            "bloklanmasin — connect basarisiz olsa bile gateway ayaga kalkar, "
            "mesajlar outbox'a yazilir, baglanti gelince retrier bosaltir."
        ),
    )
    nats_publish_timeout_sec: float = Field(
        default=0.5,
        ge=0.1,
        le=30.0,
        description=(
            "JetStream publish bekleme suresi (sn). Tek mesaj icin. Tipik "
            "yerel cluster'da <10ms cevap; agresif kucuk timeout broker "
            "yavasladiginda mesajin outbox'a hizla dusmesini saglar. 0.5sn "
            "default: 100 cihaz x 30 sinyal paralel cycle'da bile cycle "
            "timeout'a (120s) zarar vermeden, broker yavasladiginda kontrollu "
            "outbox akisina geciyor. Slow-network deploylar icin >=2.0 "
            "manuel set edilebilir."
        ),
    )
    # Geriye uyumluluk: nats_dual_publish_enabled artik anlamsiz cunku JetStream
    # tek yol. Eski .env'ler kirilmasin diye field tutulur ama goz ardi edilir.
    # Default False — yeni deploy'lar bu flag'i aktive etmemeli; bilincli set
    # eden operator startup'ta DEPRECATED uyarisi alir (boot warning).
    nats_dual_publish_enabled: bool = Field(
        default=False,
        description=(
            "DEPRECATED — JetStream artik tek primary yol; bu bayrak goz "
            "ardi edilir. Eski .env'lerdeki 'true' degerleri sessizce kabul "
            "edilir; main.py boot'ta WARN log atar."
        ),
    )

    # ----- RabbitMQ (LEGACY — telemetri akisindan kaldirildi) -----------------
    # Bu alanlar yalnizca geriye uyumluluk + log redaction icin saklaniyor;
    # gateway artik RabbitMQ'ya BAGLANMIYOR. Alarm mesajlari backend tarafinda
    # RabbitMQ'da kalmaya devam ediyor (gateway onunla ilgilenmez). .env'de
    # RABBITMQ_URL bos kalabilir — sadece eski deploylar icin tutuluyor.
    rabbitmq_url: str = Field(
        default="",
        description="LEGACY/DEPRECATED — gateway artik RabbitMQ kullanmiyor. Bos birakin.",
    )
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
    # Cycle interval: gateway'in due_devices kontrolu icin "uyanma" araligi.
    # Eski 5sn frontend gecikmesinin ana sebebiydi; 1sn ile gateway saniyede
    # bir cihaz queue'sunu kontrol eder. Ek I/O yuku yok cunku event-driven
    # mod cihazda yeni veri yoksa adapter'dan "no_change" dönuyor (publish
    # olmuyor).
    default_poll_interval_sec: int = Field(default=1, ge=1, le=3600)
    # Paralelizm: bir cycle'da kac cihaz aynı anda okunur. 100 cihaz/gateway
    # senaryosunda 25 yetersiz; tek cycle'da 100 cihaz paralel okuma yapilirsa
    # her cihazin yanit suresi <100ms oldugu icin cycle 1sn altinda biter.
    max_parallel_devices: int = Field(default=100, ge=1, le=500)
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
    dnp3_manager_threads: int = Field(
        default=0,
        ge=0,
        le=64,
        description=(
            "yadnp3 (opendnp3.DNP3Manager) icin IO thread sayisi. 0 = otomatik "
            "(adapter heuristic, minimum 4). 100 cihazli instance icin 4-8 "
            "onerilir; daha azinda thread doyumu olur (eski sabit 2 yetersiz)."
        ),
    )

    # ----- Logging -------------------------------------------------------------
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="text", description="text | json")
    # Default FALSE — token konsolda tam metin gozukurse docker logs'ta kalir;
    # log aggregator'a (ELK, Loki) gidip leak olabilir. Kasitli "false" guvenli.
    # Ihtiyac halinde .env: SHOW_GATEWAY_TOKEN_ON_START=true ile geri acilabilir.
    show_gateway_token_on_start: bool = Field(default=False)

    # Rotating dosya log'lama. NSSM/Windows servis stdout'u tek dosyaya yonlendirir
    # ama rotasyon YAPMAZ — 600 cihazli yuk altinda saatler icinde disk dolar.
    # LOG_FILE_PATH set edilirse her gateway instance kendi rotating dosyasina
    # yazar. {gateway_code} yer tutucu otomatik resolve edilir; boylece tek
    # template ile coklu instance'lar ayrik dosyalara yazar.
    log_file_path: str = Field(
        default="",
        description=(
            "Rotating log dosyasi yolu. Bos ise sadece stdout'a yazilir (mevcut "
            "davranis, Docker icin uygundur). Windows NSSM kurulumlarinda set "
            "edin: orn. 'C:/ProgramData/horstmann/dnp3-gateway/{gateway_code}.log'. "
            "Yer tutucular: {gateway_code}, {instance_id}."
        ),
    )
    log_file_max_bytes: int = Field(
        default=20 * 1024 * 1024,  # 20 MB
        ge=1024 * 1024,  # 1 MB min
        le=2 * 1024 * 1024 * 1024,  # 2 GB max
        description="Tek log dosyasi maksimum boyutu (byte). Asilirsa rotate.",
    )
    log_file_backup_count: int = Field(
        default=10,
        ge=1,
        le=100,
        description=(
            "Kac eski log dosyasi tutulsun (rotation sonrasi). 10 x 20MB = 200MB "
            "instance basina ust sinir."
        ),
    )

    # ----- Backend HTTP client guvenlik ---------------------------------------
    # Backend config response icin maksimum boyut (10 MB). Ustu raise eder
    # (memory DoS koruma). Tipik 100 cihaz config'i ~50KB; 10MB cok cok yeterli.
    backend_response_max_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=64 * 1024,  # min 64KB
        le=200 * 1024 * 1024,  # max 200MB
        description="Backend config response max size (DoS koruma)",
    )

    # ----- Validators ---------------------------------------------------------
    @field_validator("dnp3_read_strategy")
    @classmethod
    def _validate_read_strategy(cls, v: str) -> str:
        valid = {"event_driven", "direct", "class0", "integrity"}
        s = (v or "").strip().lower()
        if s not in valid:
            raise ValueError(
                f"DNP3_READ_STRATEGY gecersiz: '{v}'. Gecerli: {sorted(valid)}"
            )
        return s

    @field_validator("dnp3_library")
    @classmethod
    def _validate_library(cls, v: str) -> str:
        valid = {"yadnp3", "dnp3py"}
        s = (v or "").strip().lower()
        if s not in valid:
            raise ValueError(
                f"DNP3_LIBRARY gecersiz: '{v}'. Gecerli: {sorted(valid)}"
            )
        return s

    @field_validator("gateway_mode")
    @classmethod
    def _validate_gateway_mode(cls, v: str) -> str:
        valid = {"mock", "dnp3"}
        s = (v or "").strip().lower()
        if s not in valid:
            raise ValueError(
                f"GATEWAY_MODE gecersiz: '{v}'. Gecerli: {sorted(valid)}"
            )
        return s

    @field_validator("log_format")
    @classmethod
    def _validate_log_format(cls, v: str) -> str:
        valid = {"text", "json"}
        s = (v or "").strip().lower()
        if s not in valid:
            raise ValueError(
                f"LOG_FORMAT gecersiz: '{v}'. Gecerli: {sorted(valid)}"
            )
        return s

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        s = (v or "INFO").strip().upper()
        if s not in valid:
            raise ValueError(
                f"LOG_LEVEL gecersiz: '{v}'. Gecerli: {sorted(valid)}"
            )
        return s

    @field_validator("backend_api_url")
    @classmethod
    def _validate_backend_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("BACKEND_API_URL bos olamaz")
        try:
            parsed = urlparse(v.strip())
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"BACKEND_API_URL parse edilemedi: {exc}") from exc
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"BACKEND_API_URL scheme http/https olmali (gelen: '{parsed.scheme}')"
            )
        if not parsed.netloc:
            raise ValueError(f"BACKEND_API_URL hostname icermiyor: '{v}'")
        return v.strip()

    @field_validator("rabbitmq_url")
    @classmethod
    def _validate_rabbitmq_url(cls, v: str) -> str:
        # LEGACY: gateway artik RabbitMQ kullanmiyor. Bos izinli; eski .env'lerden
        # gelen amqp:// degerleri de gecerli (sadece doğrulanir, kullanilmaz).
        s = (v or "").strip()
        if not s:
            return ""
        try:
            parsed = urlparse(s)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"RABBITMQ_URL parse edilemedi: {exc}") from exc
        if parsed.scheme not in ("amqp", "amqps"):
            raise ValueError(
                f"RABBITMQ_URL scheme amqp/amqps olmali (gelen: '{parsed.scheme}')"
            )
        return s

    @model_validator(mode="after")
    def _validate_production_safeguards(self) -> "Settings":
        """Production / staging ortaminda guvenlik kontrolleri.

        * TLS verify ZORUNLU — kapatilirsa SystemExit (MITM koruma).
        * BACKEND_API_URL https:// olmali (production/staging) — clear-text
          gateway token MITM koruma.
        * NATS_URL bos olamaz (production); tls:// onerilir, nats://
          (clear-text) kabul ama uyari log atilir. Gateway 0.4.x'te NATS
          telemetri akisinin tek yoludur, eksikse cihaz verisi cati'ya
          ulasmaz.
        * Token MIN length staging=16, production=32.
        * SHOW_GATEWAY_TOKEN_ON_START production'da kapali olmali — leak riski.
        * GATEWAY_REFRESH_TOKEN, GATEWAY_TOKEN'dan FARKLI olmali — ayni ise
          backend tokeni leak olunca uzaktan tum cihazlari yorma kapisi acilir.

        NOT: RABBITMQ_URL artik gateway tarafindan kullanilmiyor (alarm/event
        akisi backend tarafinda kalir). Bu validator RabbitMQ scheme'i kontrol
        etmez; gateway baglanti kurmaz.
        """
        env = (self.app_environment or "development").strip().lower()
        is_prod = env in ("production", "prod")
        is_stg_or_prod = is_prod or env in ("staging", "stg")
        if is_stg_or_prod:
            if not self.backend_api_verify_ssl:
                raise ValueError(
                    f"GUVENLIK: APP_ENVIRONMENT={env} ortaminda "
                    "BACKEND_API_VERIFY_SSL=False olamaz (MITM riski). "
                    "Sertifika sorunu varsa BACKEND_API_CA_PATH ile kendi CA bundle'inizi verin."
                )
            if not self.backend_api_url.lower().startswith("https://"):
                raise ValueError(
                    f"GUVENLIK: APP_ENVIRONMENT={env} ortaminda "
                    f"BACKEND_API_URL https:// olmali (gelen: {self.backend_api_url!r}). "
                    "Clear-text HTTP uzerinden gateway token MITM ile calinabilir."
                )
            if is_prod:
                # NATS scheme kontrolu: production'da boş olamaz; tls://
                # onerilir, nats:// (clear-text) kabul ama riskli. 0.4.x'te
                # NATS telemetri akisinin TEK yolu.
                nats_url_lower = (self.nats_url or "").strip().lower()
                if not nats_url_lower:
                    raise ValueError(
                        "GUVENLIK: APP_ENVIRONMENT=production'da NATS_URL "
                        "bos olamaz. Gateway telemetriyi JetStream'e basar; "
                        "URL set edilmezse hicbir telemetri cati'ya iletilmez."
                    )
                if not nats_url_lower.startswith(("tls://", "nats://")):
                    raise ValueError(
                        f"GUVENLIK: APP_ENVIRONMENT=production'da NATS_URL "
                        f"tls:// veya nats:// scheme olmali (gelen: {self.nats_url!r})."
                    )
                if self.show_gateway_token_on_start:
                    raise ValueError(
                        "GUVENLIK: APP_ENVIRONMENT=production'da "
                        "SHOW_GATEWAY_TOKEN_ON_START=True olamaz (token log'da leak olur). "
                        "Token'i .env'den dogrulayin."
                    )
                if (
                    self.gateway_refresh_token
                    and self.gateway_token
                    and self.gateway_refresh_token.strip() == self.gateway_token.strip()
                ):
                    raise ValueError(
                        "GUVENLIK: APP_ENVIRONMENT=production'da GATEWAY_REFRESH_TOKEN, "
                        "GATEWAY_TOKEN ile AYNI olamaz. Rol ayrimi icin farkli, "
                        "yuksek-entropy bir token kullanin."
                    )
        return self

    @property
    def is_mock_mode(self) -> bool:
        return self.gateway_mode.strip().lower() == "mock"

    @property
    def is_dnp3_mode(self) -> bool:
        return self.gateway_mode.strip().lower() == "dnp3"


settings = Settings()
