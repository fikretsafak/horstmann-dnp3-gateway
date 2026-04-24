# Tag Engine Service

Gateway tarafindan gelen `telemetry.raw_received` eventlerini tuketir, normalize eder ve `telemetry.received` olarak RabbitMQ'ya yayinlar.

## Calistirma

1. `cd apps/tag-engine`
2. `py -3.10 -m pip install -r requirements.txt`
3. `py -3.10 -m tag_engine.main`
