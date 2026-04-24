# Event-Driven Validation Checklist

Bu kontrol listesi yeni gateway + mikroservis ayrisimi sonrasi temel dogrulama adimlarini icerir.

## 1) Temel ayaga kalkis

1. Service panelden sirayla baslat:
   - PostgreSQL
   - RabbitMQ
   - Backend API
   - Collector DNP3 Gateway
   - Tag Engine Service
   - Alarm Service
   - Notification Service
2. Saglik kontrolleri:
   - API: `127.0.0.1:8000`
  - Collector DNP3: `127.0.0.1:8020`
   - Tag: `127.0.0.1:8011`
   - Alarm: `127.0.0.1:8012`
  - Notification: `127.0.0.1:8013`

## 2) Uctan uca event zinciri

Beklenen zincir:

`gateway-read -> telemetry.raw_received -> telemetry.received -> alarm.created -> notification-dispatch`

Kontrol:
- `system_events` tablosunda `gateway_batch_ingested`, `telemetry_received`, `alarm_ingested_internal` olaylarini izle.
- RabbitMQ uzerinde ilgili queue'larda kalici birikme olmadigini dogrula.

## 3) Retry ve DLQ

1. Notification servisini gecici olarak kapat.
2. Yeni telemetry akisi olustur.
3. RabbitMQ'da `alarm.created` kuyrugunda birikme oldugunu dogrula.
4. Servisi tekrar actiginda biriken mesajlarin tuketildigini dogrula.

## 4) Dayaniklilik

1. Tag/Alarm/Notification servislerinden birini zorla durdur.
2. Bir sure telemetry akmaya devam etsin.
3. Workeri tekrar baslat.
4. Mesajlarin durable queue'dan tuketilmeye devam ettigini dogrula.

## 5) Idempotensi

1. Ayni `message_id` ile ayni payload'i iki kez publish et.
2. `processed_messages` tablosunda tek etkili islem oldugunu ve duplicate uretmedigini dogrula.
