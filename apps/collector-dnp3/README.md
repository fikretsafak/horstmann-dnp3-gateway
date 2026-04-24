# Collector DNP3 (Gateway Service)

Bu servis **gateway katmanidir**. Backend API'den kendi konfigurasyonunu ve cihaz
listesini cekerek ilgili cihazlari poll eder ve urettigi telemetri verisini
RabbitMQ uzerinden `telemetry.raw_received` topic'ine publish eder. Bu event'i
tag-engine tuketir.

Ayni makinada birden fazla instance calistirilabilir: her instance icin
`GATEWAY_CODE`, `GATEWAY_TOKEN` ve `WORKER_HEALTH_PORT` degerleri benzersiz
secilmelidir.

## Mimari akis

```
backend-api   <── /gateways/{code}/config (X-Gateway-Token)
     |
     |   response = {
     |     devices: [...],                    # gateway'e atanan cihazlar
     |     signals: [...],                    # STANDART sinyal katalogu (tum cihazlar icin ortak)
     |     config_version: "<sha1-12>"        # degisim algilama
     |   }
     v
collector-dnp3  ──► RabbitMQ (telemetry.raw_received)  ──► tag-engine
```

- Backend API, `/api/v1/gateways/{code}/config` endpoint'i ile gateway metadatasini,
  o gateway'e bagli cihazlari **ve standart sinyal katalogunu** doner.
- Sinyal katalogu sistem capinda ortaktir; collector her cihaz icin ayni adres
  haritasini kullanir. Kurulumcu rolu UI uzerinden adresleri degistirebilir.
- Collector bu config'i `CONFIG_REFRESH_SEC` araliklariyla yenileyerek cihaz
  ve sinyal listesinin dinamik olarak degismesine izin verir.
- Her cihaz kendi `poll_interval_sec`'i ile sorgulanir; her poll'da sinyal
  listesi uzerinden tum sinyaller okunur.

## Calistirma

1. `cd apps/collector-dnp3`
2. `py -3.10 -m pip install -r requirements.txt`
3. Ortam degiskenlerini ayarlayin (asagidaki ornege bakin).
4. `py -3.10 -m collector_dnp3.main`

## Ortam degiskenleri

| Key | Varsayilan | Aciklama |
| --- | --- | --- |
| `GATEWAY_CODE` | `GW-001` | Bu gateway instance'inin kodu. Backend'deki `gateways` tablosunda olmali. |
| `GATEWAY_TOKEN` | `gw-default-token` | Gateway icin kayitli `token`. Config endpoint'ine gonderilir. |
| `GATEWAY_MODE` | `mock` | `mock` = rastgele deger uret, `dnp3` = gercek DNP3 (ileride) |
| `BACKEND_API_URL` | `http://127.0.0.1:8000/api/v1` | Backend API base URL. |
| `CONFIG_REFRESH_SEC` | `30` | Config kac saniyede bir yenilensin. |
| `CONFIG_TIMEOUT_SEC` | `5` | Backend HTTP timeout. |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/` | RabbitMQ baglanti URL'i. |
| `RABBITMQ_EXCHANGE` | `hsl.events` | Topic exchange adi. |
| `RABBITMQ_ROUTING_KEY` | `telemetry.raw_received` | Yayinlanan routing key. |
| `WORKER_HEALTH_HOST` | `127.0.0.1` | Health HTTP sunucusu host'u. |
| `WORKER_HEALTH_PORT` | `8020` | Health endpoint portu. |
| `DEFAULT_POLL_INTERVAL_SEC` | `5` | Ana dongunun varsayilan bekleme suresi. |
| `SIGNAL_KEYS_CSV` | `voltage,current,power` | Bilinmeyen signal profile icin fallback sinyal listesi. |

## Coklu gateway ornegi

Ayni makinede iki gateway calisitirmak icin (PowerShell):

```powershell
# 1. gateway
$env:GATEWAY_CODE="GW-001"
$env:GATEWAY_TOKEN="gw-001-token"
$env:WORKER_HEALTH_PORT="8020"
py -3.10 -m collector_dnp3.main
```

```powershell
# 2. gateway (baska bir PowerShell pencerede)
$env:GATEWAY_CODE="GW-002"
$env:GATEWAY_TOKEN="gw-002-token"
$env:WORKER_HEALTH_PORT="8021"
py -3.10 -m collector_dnp3.main
```

## Health endpoint

`GET http://127.0.0.1:<WORKER_HEALTH_PORT>/health` — gateway_code, aktif cihaz
sayisi ve config_version bilgilerini doner. Service control panel bu endpoint'i
poll ederek gateway durumunu gosterir.
