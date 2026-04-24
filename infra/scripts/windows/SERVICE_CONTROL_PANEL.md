# Service Control Panel (Windows)

Bu panel; altyapı servisleri + Python microservice'leri + gateway instance'larını
**tek pencereden, CMD kullanmadan** yönetmek için tasarlanmıştır.

## Yönetilen Servisler

- PostgreSQL (Windows service)
- RabbitMQ (Windows service)
- Backend API (FastAPI process)
- Tag Engine Service (process)
- Alarm Service (process)
- Notification Service (process)
- Frontend Web (Vite dev server)

Gateway'ler ayrı "Gateway Yönetimi" sekmesinde tutulur ve birden fazla gateway
tanımlanabilir.

## Dosyalar

- `infra/scripts/windows/service_control_panel.py`
- `infra/scripts/windows/service_control_panel.config.json`

## Çalıştırma

1. `service_control_panel.config.json` içindeki yolları kendi ortamına göre
   kontrol et (özellikle `working_dir` alanları).
2. `windows_service_name` alanlarının makinedeki servis isimleri ile **bire bir
   aynı** olduğundan emin ol (örn. `postgresql-x64-16`, `RabbitMQ`).
3. Paneli başlat:

```powershell
py -3.10 "infra/scripts/windows/service_control_panel.py"
```

İlk kullanımda şu sırayı öneririz:

1. **Kurulum** sekmesi → *Tüm Bağımlılıkları Kur* (pip + npm install hepsi)
2. **Kurulum** sekmesi → *Kurulumcu (Installer) Hesabı Oluştur / Sıfırla*
3. **Kurulum** sekmesi → *Varsayılan Sinyalleri Seed Et*
4. **Hızlı Aksiyonlar** → *Akıllı Başlat (sıralı)*

## Sekmeler

### Temel Servisler
Core microservice'ler. Her satırda `Başlat`, `Durdur` ve `Yeniden Başlat`
butonları var.

### Gateway Yönetimi
Collector-DNP3 instance'ları. Birden fazla gateway ekleyip her biri için
`GATEWAY_CODE`, `GATEWAY_TOKEN` ve `WORKER_HEALTH_PORT` ile yönet.

### Kurulum
CMD'e gerek kalmadan:
- Her servis için `pip install -r requirements.txt`
- Frontend için `npm install`
- Kurulumcu hesabı oluştur / şifresini sıfırla (`scripts/seed_installer.py`)
- Varsayılan Horstmann SN2 sinyallerini seed et

Her görev arka planda çalışır; çıktıyı `Çıktıyı Göster` ile canlı takip edebilirsin.

### Olay Günlüğü
Tüm başlatma, durdurma, yeniden başlatma, sağlık değişimi ve hata olayları
merkezi bir zaman çizelgesinde görünür. Sütunlar: `Zaman`, `Seviye`
(INFO/OK/WARN/ERROR), `Kaynak` (ilgili servis adı ya da "Panel"), `Mesaj`.
- `Otomatik aşağı kaydır` açıkken en son olay her zaman ekranda kalır.
- `Temizle` tüm satırları siler.
- `Dışa Aktar` günlüğü `olay_gunlugu_YYYYMMDD_HHMMSS.txt` olarak kaydeder —
  sistemi başkasıyla paylaşırken veya destek talebi açarken kullanışlıdır.

Durum satırında görünen her bildirim otomatik olarak Olay Günlüğü'ne de
düşer; ayrıca arka plan poll döngüsü her servisin durum/sağlık değişimini
de bu sekmeye kaydeder.

## Performans Notları (v2.18.0+)

- **Tüm aksiyonlar arka plan thread'inde** çalışır — UI asla donmaz.
- **Akıllı Başlat**: Windows servisleri (PostgreSQL, RabbitMQ) yalnızca
  `STOPPED` ise başlatılmaya çalışılır; zaten çalışıyorlarsa dokunulmaz.
  Admin yetki yoksa uyarı gösterilir ama akış durmaz — backend ve diğer
  servisler yine sırayla ayağa kaldırılır.
- **Toplu `Uygulamaları Durdur` / `Uygulamaları Yeniden Başlat` butonları
  PostgreSQL ve RabbitMQ'ya dokunmaz.** Bunlar altyapı kabul edilir ve
  sürekli açık kalması beklenir. İhtiyaç hâlinde satır bazlı `Durdur`
  butonu ile tek tek durdurulabilir (bu durumda PowerShell'i Admin olarak
  çalıştırmak gerekir).
- **`ÇALIŞIYOR (dış)` durumundaki servisler de durdurulabilir.** Panel
  kendi başlatmadığı (veya panel yeniden açılınca PID'i kaybolmuş)
  prosesleri `Get-NetTCPConnection` ile health port üzerinden bulup
  `taskkill /T /F` uygular. Bu sayede Tag Engine, Frontend vb. panel
  dışında başlatılmış servisler de tek tıkla durdurulur.
- **Child process tree** Windows'ta `taskkill /T /F /PID` ile kapatılır;
  `npm run dev` gibi alt proses spawn eden servisler bırakılmaz.
- **Ring-buffer log** her servis için son 500 satırı tutar; kurulum
  adımlarının `Çıktıyı Göster` penceresi canlı akar.
- **PowerShell çağrıları** hiçbir zaman console penceresi açmaz
  (`CREATE_NO_WINDOW`).

## Harici Olarak Kurulmuş Servisler (RabbitMQ / PostgreSQL)

Panel **RabbitMQ veya PostgreSQL'i kurmaz.** Bunları sen kurdun; panel
sadece Windows Service Manager'daki mevcut kayda `Start-Service` /
`Stop-Service` komutu gönderir. `service_control_panel.config.json`
içindeki `windows_service_name` alanı bu kaydın adıdır (örn. `RabbitMQ`,
`postgresql-x64-16`).

`Cannot open RabbitMQ service on computer '.'` gibi bir hata görürsen:

1. Paneli yönetici (Admin) olarak çalıştırdığından emin ol, **veya**
2. Bu servisleri Windows Service Manager'dan yönet ve paneldeki toplu
   durdur/yeniden başlat butonlarına güven — bunlar zaten RabbitMQ ve
   PostgreSQL'e dokunmuyor.

## Durum ve Sağlık Göstergeleri

- **Durum** alanı:
  - `ÇALIŞIYOR`: panel tarafından başlatılan process hâlâ açık.
  - `ÇALIŞIYOR (dış)`: servis ayakta ama bu process başka bir ortamdan (örn.
    el ile açılmış terminal, Windows Service Manager) başlatılmış.
  - `BAŞLATILIYOR`: start komutu gönderildi, henüz yanıt alınmadı.
  - `DURDU` / `SERVİS BULUNAMADI`: port kapalı / Windows'ta servis kayıtlı değil.
- **Sağlık** alanı: belirtilen host/port için TCP connect testi
  (`UP` / `ERİŞİLEMİYOR`).

Health port'ları:

| Servis | Port |
|---|---|
| Backend API | 8000 |
| Tag Engine | 8011 |
| Alarm Service | 8012 |
| Notification Service | 8013 |
| Frontend Web | 5173 |
| Collector DNP3 GW-001 | 8020 |
| Collector DNP3 GW-002 | 8021 |

## Yeni Gateway Eklemek

`service_control_panel.config.json` → `gateways` listesine yeni blok ekle:

```json
{
  "name": "Collector DNP3 Gateway - GW-003",
  "type": "process",
  "working_dir": "C:/.../apps/collector-dnp3",
  "command": ["py", "-3.10", "-m", "collector_dnp3.main"],
  "env": {
    "GATEWAY_CODE": "GW-003",
    "GATEWAY_TOKEN": "gw-003-token",
    "WORKER_HEALTH_PORT": "8022"
  },
  "health_host": "127.0.0.1",
  "health_port": 8022
}
```

Aynı `GATEWAY_CODE`'un backend tarafında `gateways` tablosuna kayıtlı olmasına
dikkat et (frontend > Mühendislik > Cihazlar sekmesinden kurulumcu ekleyebilir).
