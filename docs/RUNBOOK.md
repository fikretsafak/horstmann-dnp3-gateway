# Runbook - DNP3 Gateway

Gunluk operasyon kontrol listesi.

## Baslatma

```powershell
cd "C:\...\Horstmann Smart Logger DNP3 Gateway"
./scripts/install.ps1       # ilk kez ya da -Recreate gerekiyorsa
./scripts/run_gateway.ps1   # .env uzerinden
```

Ayni makinede birden fazla gateway:

```powershell
./scripts/run_gateway.ps1 -GatewayCode GW-001 -GatewayToken tok-1 -HealthPort 8020
./scripts/run_gateway.ps1 -GatewayCode GW-002 -GatewayToken tok-2 -HealthPort 8021
```

## Saglik dogrulama

```powershell
Invoke-RestMethod http://127.0.0.1:8020/health | ConvertTo-Json -Depth 5
```

Ciktida dikkat edilecek alanlar:

| Alan | Beklenen |
| --- | --- |
| `status` | "ok" (config alindi), "starting" (henuz alinmadi) |
| `config.active` | `true` |
| `config.device_count` | 1 veya daha fazla |
| `config.signal_count` | Horstmann SN2 setinde tipik 180-220 |
| `config.config_version` | 12 karakterli hash; loglarda aynisini gorursunuz |

## Log izleme

```powershell
# PID'e gore process log'u (stdout) ayri bir terminalde.
# Servis olarak calistirildiysa: C:\ProgramData\horstmann\dnp3-gateway\current.log
Get-Content "$env:ProgramData\horstmann\dnp3-gateway\current.log" -Tail 200 -Wait
```

Anahtar log etiketleri:

| Etiket | Anlam |
| --- | --- |
| `dnp3_gateway_starting` | Servis acildi |
| `config_refresh gateway=.. version=..` | Backend yeni config dondurdu |
| `gateway_polling_resumed/suspended` | is_active degisti |
| `poll_cycle gateway=.. published=..` | Bu cycle'da yayinlanan mesaj sayisi |
| `rabbit_publisher_channel_opened` | AMQP kanali yeniden kuruldu |
| `dnp3_read_failed device=..` | Tek cihaz bazli okuma hatasi |

## Sik sorunlar

### Backend 401

```
config_refresh_error gateway=GW-001 error=config request returned 401: Invalid gateway token
```

`.env` icindeki `GATEWAY_TOKEN` backend'deki `gateways.token` ile eslesmeli.
Kontrol paneli -> Mühendislik -> Gateway Yonetimi uzerinden tokeni kopyalayin.

### RabbitMQ connection refused

```
rabbit_publisher_connection_close_error ...
```

- RabbitMQ servisi calisiyor mu?
- `RABBITMQ_URL` dogru IP + kullanici/parola icermeli.

### DNP3 `get_db_by_group bulunamadi`

`dnp3-python` surumu API degisikligi ile uyumsuz. Alternatifler:

1. Surum sabitleyin: `pip install dnp3-python==0.2.5`
2. Gecici olarak `GATEWAY_MODE=mock` ile devam edip cati tarafini test edin.

### is_active=False, yayin durmus

Operator dashboard/kontrol paneli uzerinden gateway'i enable'layin. Collector
bir sonraki `CONFIG_REFRESH_SEC` cevriminde (varsayilan 30 sn) yayina geri doner.

## Servis olarak kurulum (Windows)

`nssm` veya `sc.exe` ile:

```powershell
# Ornek: nssm ile
nssm install HorstmannDnp3Gateway `
    "C:\Projeler\Horstmann Smart Logger DNP3 Gateway\.venv\Scripts\python.exe" `
    "-m dnp3_gateway"
nssm set HorstmannDnp3Gateway AppDirectory "C:\Projeler\Horstmann Smart Logger DNP3 Gateway"
nssm set HorstmannDnp3Gateway AppStdout "$env:ProgramData\horstmann\dnp3-gateway\current.log"
nssm set HorstmannDnp3Gateway AppStderr "$env:ProgramData\horstmann\dnp3-gateway\current.log"
nssm set HorstmannDnp3Gateway Start SERVICE_AUTO_START
nssm start HorstmannDnp3Gateway
```
