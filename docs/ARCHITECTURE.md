# Mimari

`dnp3_gateway`, Horstmann Smart Logger cati yaziliminin **saha gateway**
katmanidir. Her instance tek bir fiziksel/lojik gateway'i temsil eder ve o
gateway'e atanmis (backend tarafinda tanimli) cihazlari DNP3 uzerinden poll
eder.

Ayni sunucu veya farkli sunucularda **yuk paylasimli** coklu instance icin
token, instance ID ve TLS kurallari bkz. [SECURITY.md](./SECURITY.md).

## Bilesen diyagrami

```
                            +--------------------+
                            |  backend-api       |
                            |  FastAPI + Postgres|
                            +----+----+----------+
                                 ^    |
      X-Gateway-Token, Code,     |    | GatewayConfigResponse
      Instance-Id, Request-Id   |    |
                                 |    v
                         +-----------------+
                         | BackendConfig-  |
                         | Client (requests)|
                         +--------+--------+
                                  |
                                  v
+----------------+         +---------------+          +---------------------+
|                |         |               |          |                     |
|  DNP3 adapter  |<--------+ GatewayState  +--------->| RabbitPublisher     |
|  (mock / real) |  due    | (thread-safe) |  payload | (pika, confirms)    |
|                | devices |               |          |                     |
+-------+--------+         +-------+-------+          +----------+----------+
        |                          ^                              |
        | DNP3 TCP                 |                              | AMQP
        v                          |                              v
+-----------------+          +---------------+            +-----------------+
|  Horstmann SN2  |          |  health HTTP  |            | RabbitMQ broker |
|  outstation(s)  |          |  /health      |            | exchange:       |
+-----------------+          +---------------+            | hsl.events      |
                                                          | rk:             |
                                                          | telemetry.raw_* |
                                                          +-----------------+
```

## Thread modeli

| Thread | Gorev |
| --- | --- |
| `main` | Poll dongusu (her `DEFAULT_POLL_INTERVAL_SEC`'de bir uyanir) |
| `config-refresh` | `BACKEND_API_URL` cagrilarak config cekilir (daemon) |
| `health-http` | `BaseHTTPServer.serve_forever` (daemon) |
| `main -> signal` | SIGINT/SIGTERM'u stop_event'e cevirir |

`GatewayState` tek mutex ile korunur. `RabbitPublisher` icin de bir mutex
vardir; boylece ayni kanal uzerinden yarisma olmaz.

## Event akisi (ozet)

```
[DNP3 Master]  --read-->  [Adapter.read_device]
                                 |
                                 v
                         SignalReading(key, source, raw, scaled, quality)
                                 |
                                 v
                     [poller.build_telemetry_payload]
                                 |
                                 v
          +--------------------------------------------------+
          | {                                                |
          |   "message_id": "uuid",                          |
          |   "correlation_id": "uuid",                      |
          |   "source_gateway": "GW-001",                    |
          |   "device_code": "DEV-001",                      |
          |   "signal_key": "master.actual_current",         |
          |   "signal_source": "master",                     |
          |   "signal_data_type": "analog",                  |
          |   "value": 1234.5,                               |
          |   "quality": "good",                             |
          |   "source_timestamp": "2026-04-24T08:00:00Z"     |
          | }                                                |
          +--------------------------------------------------+
                                 |
                                 v
                       AMQP basic_publish()
                           exchange=hsl.events
                           routing_key=telemetry.raw_received
                                 |
                                 v
                           [ tag-engine ]
```

Bu payload, `Horstman Smart Logger/packages/shared-contracts/telemetry-contract.json`
semasi ile birebir uyumludur. Ek olarak `signal_source` ve `signal_data_type`
alanlari tag-engine ve alarm-service'e master/sat01/sat02 ayrimini ve
binary-counter ayrimini analamakta yardimci olur.

## Hata yonetimi

- **Backend erisimi yoksa**: `config-refresh` thread'i exception loglar ve
  bir sonraki cevrimi bekler. Poll dongusu son bilinen state ile calismaya
  devam eder (is_active False ise yayinlamaz).
- **RabbitMQ bağlantisi kopmus**: `RabbitPublisher._force_close()` kanali
  sifirlar; `poller` bir sonraki publish denemesinde adapter yeniden
  baglanir. Aradan gecen sirada mesaj kaybedilir; kritik ise DNP3 event
  class'indan gelen yeni event bir sonraki cycle'da tekrar yayinlanacaktir.
  (Kalici kayip istemiyorsaniz local on-disk retry kuyruk eklenmelidir — bu
  roadmap'tedir, bkz `Roadmap` bolumu.)
- **Bir cihaz zaman asimina ugrarsa**: `poll_device` exception'i yakalar;
  sadece o cihazin bu cycle'i kaybolur, digerleri devam eder. Birkaç cycle
  sonra backend `communication_status` uzerinden bunu operator dashboard'da
  `offline` olarak gosterir (bu hesaplama tag-engine/alarm-service'te
  yapilir; gateway sadece raw event uretir).

## Konfigurasyon versiyonlama

Backend `config_version` hash'i (sha1) doner. Gateway bu degeri takip eder;
sadece degisince "configuration changed" log satiri dusurulur ve cihaz
listesinin yeni hali tum state ile degistirilir. Boylece:

- Yeni cihaz eklemesi anlik yansir (en fazla `CONFIG_REFRESH_SEC` gecikme).
- Sinyal katalogu degisikligi (DNP3 adresi, scale) restart gerektirmez.
- Gateway pasif hale getirildiginde (`is_active=False`) collector ayakta kalir,
  sadece yayin durur.

## Roadmap

- **Event subscription (Class 1/2/3)**: Su an sadece integrity poll ile
  cache okuyoruz. `opendnp3` klasik olarak class events'i push edebilir;
  gerekirse adapter `push` callback'i ile `RabbitPublisher`'a dusurulebilir.
- **Local retry queue**: RabbitMQ uzun sureli offline kalirsa lokal SQLite
  tabanli outbox kurulup broker ayaga kalkinca drain edilebilir.
- **Command downlink**: Backend'den gelen `binary_output` / `analog_output`
  komutlari (`master.cmd_*` sinyalleri) icin ayri bir AMQP consumer
  eklenip `Dnp3DeviceSession.operate()` akisi baglanabilir.
- **TLS + PKI**: `DNP3 over TLS` yada site-to-site VPN icin transport
  katmaninda sartli aktifligi destekleyecek ayarlar.
