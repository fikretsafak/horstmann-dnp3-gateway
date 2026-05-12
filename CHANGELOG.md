# Changelog

Semver'a gore tutulur. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.4.5] - 2026-05-12

### Changed — production validator esnetildi (private network HTTP)
- **BACKEND_API_URL/NATS_URL production validator'u** artik host bazli karar
  veriyor: private/loopback ag (RFC1918, 127.x, *.local, *.lan, *.internal,
  localhost) icin clear-text http://+nats:// kabul; public host icin TLS
  hala zorunlu. Onceki halde "production" ortaminda her http:// reddedildigi
  icin internal IP'de calisan saha deploylari APP_ENVIRONMENT=staging'e
  dusmek zorunda kaliyordu.

### Added — bilincli plaintext opt-out
- **`GATEWAY_INSECURE_ALLOW_PLAINTEXT`** bayragi (default FALSE). Public
  host'a clear-text HTTP/nats:// gecici izin verir; boot'ta loud WARN log
  atilir. Saha senaryosu: backend henuz Caddy/LE ile TLS'lenmeden public
  IP'de calisirken gateway'i ayaga kaldirmak icin. Plan: TLS kurulunca
  bayragi kaldir.

## [0.4.4] - 2026-05-12

### Fixed — render_compose.py + saha template'leri (cutover follow-up)
- **`scripts/render_compose.py`**: `--rabbitmq-url` argumani `--nats-url`
  olarak yenilendi; `replacements` sozlugu `{{NATS_URL}}` yer tutucusu
  kullanir (compose template'i ile uyumlu). Onceki halde template
  `{{NATS_URL}}` istiyor ama renderer `RABBITMQ_URL` veriyordu — render
  `RenderError` ile crash ediyordu. Backend "yeni gateway" akisi ve CLI
  artik calisir.
- **`docker/.env.template`**: `RABBITMQ_URL` blogu `NATS_URL` ile
  degistirildi; `DNP3_LIBRARY` default `dnp3py` (legacy) -> `yadnp3`
  (onerilen). Production validator `NATS_URL` bos olmasini reddediyor.
- **`scripts/new_gateway.ps1`**: `-RabbitUrl` parametresi `-NatsUrl` ile
  degistirildi; uretilen .env dosyasi `NATS_URL` + `NATS_SUBJECT_PREFIX`
  yazar, `RABBITMQ_URL` artik yazilmaz.
- **`pyproject.toml`**: `nats-py>=2.6,<3` zorunlu dependency olarak
  eklendi; `pika` legacy-rabbit optional-dependency'sine tasindi.
  `requirements.txt`'nin runtime davranisi degismedi (oradaki pika
  satiri rollback amaciyla durmaya devam ediyor).

### Notes
- Saha gateway'leri `:latest` image cektikleri icin bu sürumun GHCR'de
  build edilmesi otomatik distribution saglar. Sahada `docker pull` +
  `docker compose up -d --force-recreate` ile alinir.

## [0.4.3] - 2026-05-11

### Security (BLOCKER seviye duzeltmeler — production hazirlik)
- **`/refresh-all` timing-safe auth + rol ayrimi**: `hmac.compare_digest` ile
  karsilastirma; ayri `GATEWAY_REFRESH_TOKEN` (bos ise endpoint devre disi).
  Eski "boyle local ise auth bypass" davranisi kaldirildi — container icinde
  `client_ip=127.0.0.1` yaniltici.
- **Token konsol/stderr leak'i kapatildi**: `new_gateway.ps1` artik token'i
  konsola yazmiyor (PSReadLine history sizmasi); sadece dosyaya yaziyor + NTFS
  ACL ile dosya izinlerini kisitliyor. `render_compose.py` token'i `--output`
  yoksa stdout'a sadece uyari ile birlikte aktariyor. `.gitignore` `.env.*`
  pattern ile genisletildi.
- **Production validator genisletildi**: prod'da `BACKEND_API_URL` https://
  zorunlu (clear-text token MITM koruma); `NATS_URL` bos olamaz + tls:// veya
  nats:// scheme; `GATEWAY_REFRESH_TOKEN` != `GATEWAY_TOKEN` (token leak
  cap'i sinirla).
- **Backend config response schema validation**: cihaz/sinyal listesi hard
  limit (1000 cihaz / 5000 sinyal), string field truncate, IP field URL/path
  injection reddi. Backend kompromize olursa gateway kontrolsuz buyume +
  log injection korur.

### Changed — CUTOVER: RabbitMQ → NATS JetStream
- **Telemetri akisi NATS JetStream'e tasindi.** Gateway artik RabbitMQ'ya
  baglanmaz; tum telemetri `e1.telemetry.raw.<gateway_code>` subject'ine
  basilir. Backend tarafindaki alarm/notification akisi RabbitMQ'da kalmaya
  devam ediyor — gateway onunla ilgilenmez.
- `JetStreamPublisher` artik primary publisher. `RabbitPublisher` modulu
  rollback senaryosu icin dosyada duruyor ama `messaging/__init__.py`'den
  export edilmiyor (explicit import gerek).
- `pika` paketi `requirements.txt`'te legacy-marked olarak duruyor; cutover'a
  guven gelince kaldirilacak.
- `nats-py>=2.6,<3` artik zorunlu runtime dependency.
- `RABBITMQ_URL` LEGACY/DEPRECATED — default bos; eski .env'lerden bozulma
  olmasin diye field tutuluyor.

### Added — DNP3 + Operasyonel
- **Recovery state machine** (yadnp3): fresh-frame onayli haberlesme
  dogrulamasi; comm_lost flap'larini onler, geri donus aninda 175 sinyalli
  full integrity poll publish'i.
- **Refresh-all endpoint**: operator tetikli "tum cihazlara sorgu at"
  (`POST /refresh-all` Bearer auth).
- **Rotating file log handler**: `LOG_FILE_PATH={gateway_code}.log` ile
  per-instance disk log; 20MB x 10 backup default (NSSM rotation eksikligini
  kapatir).
- **JetStream resilience**: thread-safe counter, background reconnect ile
  resource leak fix, ready=False olunca explicit raise (sessiz drop yok →
  outbox at-least-once).
- **Cycle ortasinda graceful shutdown**: `run_poll_cycle` artik `stop_event`
  argumani aliyor; seri ve paralel yolda 2sn quantum ile check eder.
- **Windows SIGBREAK handler**: NSSM stop'tan tetiklenen Ctrl+Break sinyali
  yakalanir.
- **Config refresh thread defansif Exception yakalama**: `ValidationError`,
  `SSLError`, `ConnectionResetError` artik thread'i sessizce oldurmuyor;
  state'e hata yazip backoff loop'a devam eder.
- **`Dnp3TelemetryReader.forget_devices` override**: legacy adapter'da silinen
  cihazlarin DNP3 session + cache temizligi.

### Fixed
- `poller.py:275` `getattr(...) and X or -1` antipattern — pending=0 durumunda
  yanlislikla -1 donuyordu. `pending_count()` public API ResilientPublisher'a
  eklendi.
- Class 0 yerine FULL integrity poll (0+1+2+3) — eksik baseline tazelemesini
  cozer (commit `2af0792`).
- `ScanClasses` imzasinda SOE handler eksikligi (commit `d65b525`).
- Recovery confirm aninda `mark_all_dirty` — gecikme azalma (commit `94c822b`).

### Tests
- `test_config_settings.py:15` default uyumlu (artik
  `show_gateway_token_on_start is False`).
- `test_auth_identity.py` production safeguard'a uyumlu test URL'leri.
- `test_config_client.py` `_DummySession` stream/raw/iter_content desteklior.
- `test_poller.py` Group 110 (string sinyal) yayinlanir kabulu.

## [0.3.5] - 2026-04-24

### Added
- `run_poll_cycle(max_parallel=...)` — `MAX_PARALLEL_DEVICES` artik poll
  dongusunde thread pool ile kullaniliyor. 100 cihazlik gateway'de seri okuma
  cycle suresini saniyeler/dakikalara cikarabiliyordu; paralel okumayla
  toplam cycle suresi okuma gecikmesinin en yavas cihazi kadar kaliyor.
- `test_run_poll_cycle_parallel_reads_all_due_devices` — 6 cihaz + 4 worker
  senaryosunda tum cihazlarin okunup `mark_read` edildigini dogrular.

### Changed
- `main.run()` artik `cfg.max_parallel_devices` degerini poll cycle'a aktariyor.
- `poller.run_poll_cycle` docstring'i paralel davranis ve publisher thread-safety
  varsayimini acikliyor.

## [0.2.2] - 2026-04-24

### Fixed / Changed
- `run_gateway.ps1` artik bos `gateway_code=` yazdirmiyor; once `scripts/show_env_summary.py`
  ile `.env` ozeti (kod, saglik portu, backend config URL).
- Baslangicta konsol banner: saglik URL, DNP3 TCP portu, coklu proses uyarisi.
- `404/401` config hatalarinda loga kisa cozum metni.
- `/health` JSON: `worker_health_port` alani.

## [0.2.1] - 2026-04-24

### Added
- Baslangicta konsola `GATEWAY_TOKEN` satiri (varsayilan tam metin);
  `SHOW_GATEWAY_TOKEN_ON_START=false` ile maskeli gosterim.

## [0.2.0] - 2026-04-24

### Added
- `dnp3_gateway.auth` — `GatewayIdentity`, kalıcı `GATEWAY_INSTANCE_ID` (veya
  `GATEWAY_STATE_DIR` altında dosya), `APP_ENVIRONMENT` ile üretim token
  uzunluğu + placeholder kontrolü.
- Her config isteğinde: `X-Gateway-Code`, `X-Gateway-Instance-Id`,
  `X-Request-Id`, `User-Agent`, `X-Gateway-Client` başlıkları.
- `BACKEND_API_VERIFY_SSL` / `BACKEND_API_CA_PATH` ile TLS doğrulama.
- `docs/SECURITY.md` — çoklu sunucu / token / RabbitMQ checklist.
- Sağlık JSON: `gateway_instance_id`, `app_environment`.

### Changed
- `BackendConfigClient` artık `GatewayIdentity` kullanır (eski token-only ctor kaldırıldı).

### Catı backend (Horstman Smart Logger)
- `GET /gateways/{code}/config`: isteğe bağlı `X-Gateway-Code` path ile
  uyuşmazsa 400 (yanlış yapılandırma / proxy erken tespiti).

## [0.1.0] - 2026-04-24

### Added
- Proje iskeleti (`src/dnp3_gateway/`, `tests/`, `scripts/`, `docs/`).
- `Settings` - pydantic-settings tabanli env + .env konfigurasyonu.
- `BackendConfigClient` - backend `/gateways/{code}/config` endpoint'i uzerinden
  cihaz listesi + standart Horstmann SN 2.0 sinyal katalogunu ceker.
- `GatewayState` - thread-safe calisma anı durumu + poll scheduler.
- `RabbitPublisher` - topic exchange + publisher-confirms + auto reconnect.
- `TelemetryReader` arayuzu + `MockTelemetryReader` (gercekci degerli).
- `Dnp3TelemetryReader` iskeleti (opendnp3 / `dnp3-python` tabanli) - 30/1/20
  object group'lari icin okuma destekli.
- `poller` - okunabilir sinyalleri filtreleyen, cihaz bazli telemetri mesaji
  uretip yayinlayan cekirdek dongu.
- `health_server` - `/health` JSON endpoint'i (status, config_version, versions).
- `main.run()` - config-refresh thread + polling loop + graceful shutdown.
- PowerShell scripts (`install.ps1`, `run_gateway.ps1`).
- 18 unit test (state, config_client, settings, mock adapter, poller).
- `docs/ARCHITECTURE.md`, `docs/RUNBOOK.md`, `README.md`.
