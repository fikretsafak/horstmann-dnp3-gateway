# Alarm Service

`telemetry.received` eventlerini dinler, **backend'den çekilen alarm kurallarına** göre eşik/debounce/histerezis bazlı değerlendirme yapar, `alarm.created` eventi yayınlar ve backend'in internal alarm endpoint'ine HTTP ile bildirir.

## Çalıştırma

1. `cd apps/alarm-service`
2. `py -3.10 -m pip install -r requirements.txt`
3. `py -3.10 -m alarm_service.main`

## Ortam Değişkenleri

| Değişken | Açıklama | Varsayılan |
| --- | --- | --- |
| `RABBITMQ_URL` | AMQP URL | `amqp://guest:guest@localhost:5672/` |
| `RABBITMQ_EXCHANGE` | Topic exchange | `hsl.events` |
| `BACKEND_API_BASE` | Backend iç endpoint base URL | `http://127.0.0.1:8000/api/v1` |
| `BACKEND_INTERNAL_ALARM_URL` | Alarm ingest endpoint URL | `http://127.0.0.1:8000/api/v1/internal/alarms` |
| `INTERNAL_SERVICE_TOKEN` | Service-to-service token | `change-me-internal-token` |
| `ALARM_RULES_REFRESH_SEC` | Kuralları yenileme aralığı (sn) | `30` |
| `WORKER_HEALTH_PORT` | Health endpoint portu | `8012` |

## Alarm Kuralı Değerlendirme

- Kurallar `/internal/alarm-rules` endpoint'inden periyodik olarak çekilir.
- Sadece `is_active=True` ve `supports_alarm=True` olan sinyallere bağlı kurallar değerlendirilir.
- `comparator` tipleri: `gt | gte | lt | lte | eq | ne | between | outside | boolean_true | boolean_false`
- `hysteresis`: kural aktifken geri dönüş eşiği `threshold ± hysteresis` ile hesaplanır (flapping önlemi).
- `debounce_sec`: kural ilk tetiklendiğinde bu süre boyunca `value` sürekli eşiği geçiyorsa alarm yayılır.
- `device_code_filter`: virgülle ayrılmış cihaz kodları; boş bırakılırsa tüm cihazlar için uygulanır.

## Health

`GET /health` → `{ "status": "ok", "rules_ready": true }`
