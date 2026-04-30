# Guvenlik ve coklu gateway dagilimi

## Kimlik modeli (ozet)

| Bilesen | Amac | Nerede tutulur |
| --- | --- | --- |
| `GATEWAY_CODE` | Is mantigi kimligi; backend `gateways.code` | `.env` / secret store, **sır değil** |
| `GATEWAY_TOKEN` | Gizli paylasim anahtari; sadece config endpoint'ine erisir | `.env` / vault / **asla** git |
| `GATEWAY_INSTANCE_ID` (opsiyonel) | Ayni kodla birden fazla makinede hata tespiti, log korelasyonu | Bos ise `GATEWAY_STATE_DIR/instance_{kod}.id` |
| `APP_ENVIRONMENT` | `development` / `staging` / `production` token sertligi | `.env` |

Yuk uzerinde **paralel N gateway** = **N ayrı `gateways` satırı** + cihazlar `device.gateway_code` ile bölüştürülür. Ayni `GATEWAY_CODE` + farkli `GATEWAY_TOKEN` calismaz (backend token satira baglidir). Ayni token'i iki farkli `GATEWAY_CODE` arasinda paylasmayin: bir token sizilirse sadece o gateway'in config'ine ulasilir.

## HTTP: backend ile sözlesme

Her config isteginde su basliklar gider (bkz. `dnp3_gateway.auth.headers`):

- `X-Gateway-Token` — gizli
- `X-Gateway-Code` — path'teki `gateway_code` ile ayni olmali (backend uyumsuzsa 400; yanlis proxy kurulumlarini yakar)
- `X-Gateway-Instance-Id` — opservabilite; backend simdilik audit icin (ileride log/metrics)
- `X-Request-Id` — tekil istek ID (Kibana/Datadog korelasyonu)
- `User-Agent: Horstmann-Dnp3Gateway/{versiyon} (env=...)`

Eski sadece-token istemcileri (`collector-dnp3`) calismaya devam eder: `X-Gateway-Code` gondermek zorunlu degil; gonderen yeni gateway ise path ile **eslesme zorunlu**.

## TLS

- Uretimde `https://` + `BACKEND_API_VERIFY_SSL=true` (varsayilan).
- Ozel CA: `BACKEND_API_CA_PATH` = PEM bundle yolu.
- Sadece local lab: gecici `BACKEND_API_VERIFY_SSL=false` (aradaki saldirgan riski — dokümante edilmis kabul).

## Token omru ve rotasyonu

1. Backend **Installer** rolu ile yeni `token` (veya ayni endpoint'te guncelleme).
2. Ilgili sunucuda `.env` guncelle (veya secret manager deploy).
3. **Servisi yeniden baslat** (process ortam degerini tekrar okur). Kisa kesinti: yeni `CONFIG_REFRESH` dongusune kadar eski proses 401 alir; loglari izleyin.
4. Ileride: `Authorization: Bearer` + kisa omurlu token (OIDC) veya mTLS (istemci sertifikasi) **aynı** `build_config_request_headers` genisletmesiyle eklenebilir.

## RabbitMQ

Broker kullanici/parolasi `RABBITMQ_URL` icinde. Uretimde:

- Her site icin **ayri vhost** veya **ayri kullanici** (ACL ile sadece kendi routelari).
- TLS (`amqps://`) ve sertifika dogrulama tercih edilir.

## Checklist: yeni sunucuya gateway

- [ ] Backend'de `gateways` kaydi: `code`, `token`, `control_host` / `control_port` (uzaktan yonetim).
- [ ] Cihazlar bu gatewaye `gateway_code` ile atanmis.
- [ ] Bu makinede `.env`: `GATEWAY_CODE` + guc token + `APP_ENVIRONMENT=production`.
- [ ] `WORKER_HEALTH_PORT` bu makine uzerinde benzersiz (aynı hostta baska instance varsa 8021, 8022, ...).
- [ ] `RABBITMQ_URL` ve TLS politikasi uygun.
- [ ] (Opsiyonel) `GATEWAY_INSTANCE_ID` = inventori/deployment id.
