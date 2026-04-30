# Horstmann Smart Logger DNP3 Gateway

**Version:** 0.2.2
**Hedef platform:** Windows Server / Windows 10+ (Linux systemd de calisabilir)
**Python:** 3.10 - 3.12

Bu proje [Horstman Smart Logger](../Horstman%20Smart%20Logger) catisinin saha
katmanidir. Her gateway instance'i **1 gateway kaydinda tanimli 100'e kadar
Horstmann SN 2.0 cihazi** ile DNP3 uzerinden haberlesir; okudugu sinyalleri
normalize ederek RabbitMQ uzerinden cati yazilima iletir. Sistem mimarisinde
toplam 6 gateway paralel calisir (6 x 100 = 600 cihaz).

```
+-----------------+                +------------------------+
| Horstmann SN2.0 |  DNP3 TCP     |                        |
|   (100 adet)    +--------------->|  dnp3_gateway (bu proje)|
+-----------------+                |                        |
                                   |  - config_client       |
                                   |  - poller              |
                                   |  - dnp3 adapter        |
                                   |  - rabbit publisher    |
                                   +-----------+------------+
                                               |
                                               | AMQP
                                               v
                          +-----------------------------------+
                          |  RabbitMQ  hsl.events             |
                          |  routing: telemetry.raw_received  |
                          +-----------------+-----------------+
                                            |
                                            v
                                   tag-engine / alarm-service
                                   dashboard & outbound
```

## Ozet

- **Otonom konfigurasyon**: Backend API `/gateways/{code}/config` endpoint'inden
  cihaz listesi + standart Horstmann SN 2.0 sinyal kataloğu cekilir. Her
  `CONFIG_REFRESH_SEC` periyodunda yenilenir, boylece yeni cihaz/sinyal/adres
  degisiklikleri gateway'i yeniden baslatmadan etkili olur.
- **Master/Sat01/Sat02 ayrimi**: Horstmann SN2 cihazinda ayni olcum birden fazla
  unite (master + 2 satellite) uzerinden gelir. Sinyal kataloğu `source` alani
  ile bu uc kaynagi ayirir; her telemetri mesajinda `signal_source` tasinir.
- **Poll bazli + event ready**: Cihaz ayarlarindaki `poll_interval_sec` ile
  integrity poll yapilir. Gelecekte class-event baglantisi icin temel hazirdir.
- **Scale + offset**: Ham deger `value = raw * scale + offset` ile gercek
  birime cevrilir ve yayinlanir.
- **Publisher confirms + reconnect**: RabbitMQ bağlantı koptuğunda otomatik
  yeniden bağlanır; delivery mode 2 (persistent) + publisher confirms aktiftir.
- **Health endpoint**: `GET /health` - kontrol paneli + orchestration tools
  icin durum (config_version, devices, is_active) gosterir.
- **Mock mod**: Fiziksel cihaz olmadan tum zincirin testi icin `GATEWAY_MODE=mock`
  secenegi vardir. Gercek mod `GATEWAY_MODE=dnp3` ile acilir.
- **Kimlik ve yuk dagitimi**: Her proses `GATEWAY_CODE` + gizli `GATEWAY_TOKEN`
  ile backend’e baglanir; token yalnizca `X-Gateway-Token` ile gider. Ayni
  sunucuda veya farkli sunucularda birden cok instance: farkli kod/ token +
  farkli health port; cihazlar backend’de `gateway_code` ile bolunur.
  Ayrintilar: [docs/SECURITY.md](./docs/SECURITY.md).

## Hizli Baslangic

### 1. Python 3.10+ ve bagimliliklar

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

### 2. Ortami yapilandir

`.env.example` -> `.env` olarak kopyalayin ve kendi backend / RabbitMQ / gateway
kodunuzu yazin. Onemli alanlar:

| Key | Amac |
| --- | --- |
| `GATEWAY_CODE` | Bu instance'in backend'de kayitli gateway kodu |
| `GATEWAY_TOKEN` | Backend `gateways.token` alaniyla ayni deger |
| `APP_ENVIRONMENT` | `development` / `staging` / `production` (uretimde guclu token zorunlulugu) |
| `GATEWAY_MODE` | `mock` (test) veya `dnp3` (saha) |
| `BACKEND_API_URL` | Cati backend-api adresi (`/api/v1` ile biter) |
| `RABBITMQ_URL` | `amqp://user:pass@host:5672/` |
| `WORKER_HEALTH_PORT` | Instance basina unique olmali (8020, 8021...) |

Tum parametrelerin aciklamasi icin [.env.example](./.env.example) dosyasina
bakin.

### 3. Gateway'i calistir

```powershell
# Windows - tek gateway
py -3.10 -m dnp3_gateway

# veya setuptools ile kurulduysa
horstmann-dnp3-gateway
```

Birden fazla gateway ayni makinede calistirilacaksa `scripts/run_gateway.ps1`
betigini kullanabilirsiniz (bkz. [scripts/README.md](./scripts/README.md)).

### 4. Saglik kontrolu

```powershell
curl http://127.0.0.1:8020/health
```

Yanit ornegi:

```json
{
  "status": "ok",
  "service": "dnp3-gateway",
  "version": "0.2.0",
  "gateway_code": "GW-001",
  "gateway_instance_id": "8f2b...-uuid",
  "app_environment": "development",
  "mode": "mock",
  "config": {
    "config_version": "ab12cd34ef56",
    "device_count": 100,
    "signal_count": 180,
    "active": true
  }
}
```

## Proje Yapisi

```
Horstmann Smart Logger DNP3 Gateway/
|-- README.md
|-- VERSION                    <- semver; mevcut surum
|-- pyproject.toml             <- paket meta ve setuptools konfigurasyonu
|-- requirements.txt           <- runtime bagimliliklar
|-- requirements-dev.txt       <- gelistirme/test bagimliliklar
|-- .env.example
|-- src/
|   `-- dnp3_gateway/
|       |-- __init__.py
|       |-- __main__.py        <- py -m dnp3_gateway
|       |-- main.py            <- ana dongu / config refresh / graceful shutdown
|       |-- config.py          <- Settings (pydantic-settings)
|       |-- logging_setup.py
|       |-- state.py           <- GatewayState (thread-safe)
|       |-- poller.py          <- Cihaz bazli poll scheduler
|       |-- health_server.py
|       |-- auth/              <- kimlik, instance_id, HTTP basliklari
|       |-- backend/
|       |   `-- config_client.py
|       |-- messaging/
|       |   `-- rabbit_publisher.py
|       `-- adapters/
|           |-- base.py        <- TelemetryReader arayuzu
|           |-- mock.py        <- Rastgele degerli mock okuyucu
|           `-- dnp3_master.py <- opendnp3 tabanli gercek okuyucu
|-- scripts/
|   |-- README.md
|   |-- run_gateway.ps1
|   `-- install.ps1
|-- tests/
|   |-- test_state.py
|   |-- test_config_client.py
|   |-- test_poller.py
|   |-- test_mock_adapter.py
|   `-- test_auth_identity.py
`-- docs/
    |-- ARCHITECTURE.md
    |-- SECURITY.md
    `-- RUNBOOK.md
```

## Versiyonlama

Versiyon numarasi `MAJOR.MINOR.PATCH` seklindedir:

- **Patch** (`0.1.1`): bugfix, kucuk yama
- **Minor** (`0.2.0`): yeni ozellik, geri-uyumlu genisleme
- **Major** (`1.0.0`): kirici degisiklik ya da 2 haneli minor'den taşma

`VERSION` dosyasi + `pyproject.toml` daima birlikte guncellenir.

## Lisans

Proprietary - Form Elektrik Ins. Muh. A.S. Tum haklari saklidir.
