# Docker ile Coklu Gateway Yonetimi

Bu dokuman Horstmann Smart Logger DNP3 Gateway'in Docker container'i olarak nasil
kurulup ayni host uzerinde N tane instance halinde yonetildigini anlatir. Hedef:
**bir Ubuntu sunucusunda 5-10 farkli sahaya bagi gateway'leri tek bir docker
engine altinda calistirmak**.

## Mimari ozeti

```
+-----------------+     +-----------------+
|  Frontend (UI)  | --> |  backend-api    |
|  Yeni Gateway + |     |  POST /gateways |
+-----------------+     |  GET  /.../docker-compose
                              |
                              v
+-----------------+     +---------------------------+
|  Gateway YAML   | <-- |  Backend renderlar:       |
|  hsl-gw-001.yml |     |  - GATEWAY_CODE/TOKEN     |
+-----------------+     |  - BACKEND_URL/RABBIT_URL |
        |                +---------------------------+
        | docker compose -f hsl-gw-001.yml up -d
        v
+----------------------+
| Ubuntu sunucu        |
|  +----------------+  |   - container 1: GW-001  port 8020
|  | docker engine  |  |   - container 2: GW-002  port 8021
|  +----------------+  |   - container N: GW-NNN  port 80NN
+----------------------+
       outbound DNP3
       tum sahalara
```

Her container:

- **Kendi `.env` ile**: GATEWAY_CODE, GATEWAY_TOKEN, BACKEND_API_URL, RABBITMQ_URL
- **Sabit container portu**: 8020 (health/metrics)
- **Farkli host portu**: 8020, 8021, 8022, ...
- **Persistent volume**: `hsl-gw-<code>-state` — instance_id + outbox SQLite
- **Outbound TCP**: 600 cihaza kadar DNP3 baglanti (host network'u uzerinden)

## 1. Image (kullaniciya hazir)

Image GitHub Container Registry'de **public** olarak yayinlanir; musteri sunucusunda
ayrica build veya `docker login` GEREKMEZ. `docker compose up -d` cagrisi ilk acilista
image'i otomatik pull eder.

```
ghcr.io/fikretsafak/horstmann-dnp3-gateway:latest    # her main push'unda taze
ghcr.io/fikretsafak/horstmann-dnp3-gateway:0.4.3     # surume kilitli
```

Image otomatik olarak `.github/workflows/release-image.yml` workflow'u tarafindan
build edilir:

| Trigger             | Etiketler                          |
|---------------------|------------------------------------|
| `main` push         | `:latest`, `:sha-<short>`         |
| `git tag v0.4.3`    | `:0.4.3`, `:0.4`, `:latest`       |

Multi-arch: `linux/amd64` + `linux/arm64`. yadnp3 (OpenDNP3 native) ile derlenir,
Horstmann SN2 string sinyalleri tam desteklenir.

### Kaynaktan build (sadece gelistirme)

Repo'ya commit yetkisi olan gelistiriciler local image build edebilir:

```bash
git clone https://github.com/fikretsafak/horstmann-dnp3-gateway.git
cd horstmann-dnp3-gateway

docker build \
    --build-arg DNP3_LIBRARY=yadnp3 \
    -t ghcr.io/fikretsafak/horstmann-dnp3-gateway:dev .
```

## 2. Yeni gateway ekle (frontend akisi)

Operator/installer arayuzde "Yeni Gateway Ekle" butonuna basar:

1. Frontend `POST /api/v1/gateways` ile kayit acar; backend rastgele 48 karakter
   token olusturur.
2. Frontend `GET /api/v1/gateways/<code>/docker-compose` ile YAML indirir.
   Sorgu parametreleri:
   - `backend_url` (zorunlu)  : Gateway'in cikacagi backend URL (orn.
     `https://hsl.formelektrik.com/api/v1`).
   - `rabbitmq_url` (zorunlu) : AMQP broker URL.
   - `host_port` (varsayilan 8020): Bu instance icin host portu.
   - `image` (varsayilan `ghcr.io/fikretsafak/horstmann-dnp3-gateway:latest`).
   - `app_environment` (varsayilan `production`).
   - `fmt` (varsayilan `compose`): `compose` veya `env`.
3. Inen dosya `hsl-gw-<code>.yml` (compose) veya `hsl-gw-<code>.env` (raw env).
4. Sunucuya kopyalanir + `docker compose -f hsl-gw-<code>.yml up -d`.

### Manuel renderleme (frontend olmadan)

Gateway repo'sunda CLI:

```bash
python scripts/render_compose.py \
    --code GW-002 \
    --token "$(python -c 'import secrets,string;print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(48)))')" \
    --name "Saha B SCADA" \
    --backend-url https://hsl.formelektrik.com/api/v1 \
    --rabbitmq-url amqp://hsl:secret@rmq.hsl.local:5672/ \
    --host-port 8021 \
    --image hsl/dnp3-gateway:0.4.3 \
    --output ./gateways/gw-002.yml
```

CLI `--token` verilmezse rastgele uretip stderr'a yazar; bu degeri backend
veritabanina ayni kod altinda eklemek operator sorumlulugundadir.

## 3. Calistirma

Ayni Ubuntu host'ta 5 gateway:

```bash
# Klasor duzeni:
gateways/
  gw-001.yml   # backend'den indirilen
  gw-002.yml
  gw-003.yml
  gw-004.yml
  gw-005.yml

for f in gateways/*.yml; do
    docker compose -f "$f" up -d
done
```

Liste:

```bash
docker ps --filter "label=org.opencontainers.image.title=horstmann-dnp3-gateway"
```

Tek bir gateway'i durdur / yeniden baslat:

```bash
docker compose -f gateways/gw-001.yml stop
docker compose -f gateways/gw-001.yml restart
docker compose -f gateways/gw-001.yml down            # container siler, volume kalir
docker compose -f gateways/gw-001.yml down -v         # volume da siler (DIKKAT)
```

Logs (tek instance):

```bash
docker logs -f hsl-gw-gw-001
# veya:
docker compose -f gateways/gw-001.yml logs -f
```

Health endpoint:

```bash
curl http://127.0.0.1:8020/health   # gw-001
curl http://127.0.0.1:8021/health   # gw-002
```

## 4. Networking

### RabbitMQ ve backend ayni host'ta ise

`compose.template.yml`'deki `networks: hsl` external degil — gateway compose
kendi ag'ini olusturur. RabbitMQ ve backend baska bir compose project'inde ise:

```bash
# Once ortak ag olustur (bir kere):
docker network create hsl

# compose.template.yml'de external: true olarak guncelle (veya
# render_compose --network external)
```

Ayni host'ta RabbitMQ ayri bir compose'da `hsl` ag'inda calistiriliyorsa
gateway'lerin compose dosyasinda `external: true` yapilmali. Aksi halde
container'lar broker'a `host.docker.internal` veya host ip'si ile baglanir.

### RabbitMQ uzakta ise

`RABBITMQ_URL=amqp://user:pass@rmq.example.com:5672/` -> herhangi bir ek ag
yapilandirmasi gerekmez. TLS icin `amqps://` ve sunucuda kok sertifika.

### DNP3 outbound TCP

Container default bridge ag'inda bile remote IP'lere outbound baglanti
kurabilir. **Saha cihazlari container'larin Docker bridge'ine erisemez** ve
gerek yok — master role outbound. Saha cihazlarinin gateway'i kabul etmesi
icin sunucu IP'si firewall'da whitelist'te olmali (DNP3 standart 20000/tcp).

### Coklu network arabirimi (advanced)

Bir sahaya ozel VLAN arabirimi varsa: `network_mode: host` kullan, port
mapping'leri kaldir, `WORKER_HEALTH_PORT` her gateway icin elle farkli ver
(8020/8021/...). Bu durum coklu instance icin biraz daha sıkıntılı; default
bridge mode'u tercih et.

## 5. Persistent state

Volume kaybolursa:

- **instance_id** yeniden uretilir -> backend log'unda "yeni baglanti" gorunur.
- **Outbox SQLite** kaybolur -> RabbitMQ'ya gonderilemeyen mesajlar gider.

Yedekleme:

```bash
# Tum gateway state volumelarini yedekle
docker run --rm \
    -v hsl-gw-gw-001-state:/src \
    -v $(pwd)/backup:/dst \
    busybox tar czf /dst/gw-001-state-$(date +%F).tgz -C /src .
```

Geri alma:

```bash
docker run --rm \
    -v hsl-gw-gw-001-state:/dst \
    -v $(pwd)/backup:/src \
    busybox tar xzf /src/gw-001-state-2026-04-29.tgz -C /dst
```

## 6. Upgrade / image yeni surum

```bash
# Tum host'ta:
docker pull hsl/dnp3-gateway:0.5.0

# Tek tek (zero-downtime: cihaz polling 5sn, kabul edilebilir):
sed -i 's/dnp3-gateway:0.4.3/dnp3-gateway:0.5.0/' gateways/gw-001.yml
docker compose -f gateways/gw-001.yml up -d
# instance saniyeler icinde yeni image'a gecer
```

Production'da bunu Ansible/script ile dongude koselendirin.

## 7. Tipik 600-cihaz kurulumu

| Sahalar | Cihaz dagilimi | Onerilen container sayisi | RAM/proses (yaklasik) |
|---------|----------------|---------------------------|------------------------|
| Tek site | 200 cihaz       | 1 container               | ~150MB                |
| 2-3 site | 600 cihaz toplam| 3 container × 200 cihaz   | ~150MB her biri       |
| Coklu yedeklilik | 600 cihaz | 3 container + 3 standby (farkli host) | ayni |

3 container yapisinda: GW-001 / GW-002 / GW-003 farkli sahalar. Backend
`gateway_code` ile her birine **ayri device listesi** verir; yuk dengeli olur,
arıza durumunda diger 2 site etkilenmez (fault isolation).

## 8. Sorun giderme

### Container baslarken `GATEWAY_CODE ve GATEWAY_TOKEN env zorunludur`

`.env` dosyasi compose'a yuklenmemis ya da `--env-file` verilmemis. Compose
icindeki `environment:` blogu zaten degerleri tasiyor; YAML render edilmeden
kullaniliyorsa o blok bos demektir.

### Health 8020 portu cevap vermiyor

```bash
docker exec -it hsl-gw-gw-001 curl http://127.0.0.1:8020/health
docker logs hsl-gw-gw-001 --tail 50
```

Konteyner ic ic erisilebiliyor ama host'tan erisilemiyor: `ports:` mapping
bozuk olabilir. `127.0.0.1:8020:8020` ise sadece localhost; uzaktan erisim
istiyorsaniz `0.0.0.0:8020:8020` veya reverse proxy.

### Backend 401 dönuyor

`GATEWAY_TOKEN` backend DB'deki `gateways.token` ile birebir ayni olmali.
Compose icindeki tirnak/escape karakterleri sorun cikarabilir; render edilmis
dosyayi acip token'i kontrol edin.

### Outbox surekli buyuyor

```bash
docker exec -it hsl-gw-gw-001 \
    sqlite3 /app/.gateway_state/outbox_GW-001.db "SELECT COUNT(*), MAX(retry_count) FROM outbox;"
```

RabbitMQ kapali ya da broker URL yanlis. `RABBITMQ_URL` duzelt + container
restart -> retrier 2 saniye icinde drenaj baslar.
