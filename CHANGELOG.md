# Changelog

Semver'a gore tutulur. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
