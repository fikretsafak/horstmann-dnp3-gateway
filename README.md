# Horstman Smart Logger Platform

**Version:** 2.20.0
Windows-first, Docker-free industrial monitoring platform starter for Horstmann Smart Navigator 2.0 devices.

## Tek Tıkla Başlatma

Servis Kontrol Paneli artık tamamen GUI odaklı:

```powershell
py -3.10 "infra/scripts/windows/service_control_panel.py"
```

Önerilen ilk çalıştırma sırası (hepsi panelden, CMD kullanmadan):

1. **Kurulum** sekmesi → *Tüm Bağımlılıkları Kur* (pip + npm install)
2. **Kurulum** sekmesi → *Kurulumcu (Installer) Hesabı Oluştur / Sıfırla*
3. **Kurulum** sekmesi → *Varsayılan Sinyalleri Seed Et*
4. **Hızlı Aksiyonlar** → *Akıllı Başlat (sıralı)*

Panel özellikleri: arka plan thread'lerde non-blocking aksiyonlar, child
process tree'yi `taskkill /T /F` ile düzgün kapatma, servis başına 500 satırlık
canlı log penceresi ve `CREATE_NO_WINDOW` ile görünmez PowerShell çağrıları.
Detay için bkz. `infra/scripts/windows/SERVICE_CONTROL_PANEL.md`.

## Roller (RBAC)

| Yetki | operator | engineer | installer |
|---|:---:|:---:|:---:|
| Canlı izleme (harita + tablo) | ✓ | ✓ | ✓ |
| Alarm / event görüntüleme + onay / reset | ✓ | ✓ | ✓ |
| Cihaz ekle / çıkar / güncelle | — | ✓ | ✓ |
| Gateway ekle / düzenle / sil | — | — | ✓ |
| Sinyal kataloğu (DNP3 adresleri, scale, supports_alarm) | — | — | ✓ |
| Alarm kuralları (eşik / hysteresis / debounce) | — | — | ✓ |
| Kullanıcı yönetimi | — | — | ✓ |
| Outbound hedefleri (REST / MQTT) | — | — | ✓ |
| Bildirim ayarları (SMTP / SMS) | — | — | ✓ |

- **operator**: yalnızca canlı izleme ve alarm ack/reset yapar.
- **engineer**: sistemi basitçe genişletip daraltır; yeni cihaz ekler / silinenleri kaldırır. Gateway/sinyal/alarm/kullanıcı ayarlarını değiştiremez.
- **installer** (süper admin): tüm altyapı, şablon ve parametre kurgusunu yönetir. **Tüm rollerde** (operator / engineer / installer) kullanıcı oluşturabilir; başka installer (süper admin) hesapları da ekleyip silebilir. Backend güvenlik gereği kullanıcı kendi hesabını silemez.

## Structure

- `apps/frontend-web`: React + TypeScript operator UI
- `apps/backend-api`: FastAPI central backend (auth + signal catalog + alarm rules)
- `apps/collector-dnp3`: DNP3 collector gateway service (standart sinyal listesini backend'den çeker)
- `apps/tag-engine`: Tag processing microservice
- `apps/alarm-service`: Alarm evaluation microservice (kural bazlı eşik/debounce)
- `apps/notification-worker`: Notification microservice
- `packages/shared-contracts`: shared payload contracts
- `infra/scripts`: Windows/Linux service scripts

## Veri akışı (özet)

```
collector-dnp3  --(telemetry.received)-->  tag-engine  --(processed)-->  alarm-service
       |                                                                         |
       +--- GET /gateways/{code}/config (signal list + device list) --- backend-api
                                                                                 |
                                                          GET /internal/alarm-rules
```

- Sinyal kataloğu tüm cihazlar için ortaktır; cihaz eklendiğinde otomatik uygulanır.
- Alarm kuralları `signal_key` bazlı template'dir; `supports_alarm=True` olan sinyalde değerlendirilir.
- `device_code_filter` alanı virgülle ayrılmış cihaz kodları ile kuralın kapsamını daraltır (boş = tüm cihazlar).

## First Run (Development)

Önerilen yol Servis Kontrol Paneli (yukarıda). Yine de manuel çalıştırmak isteyenler için:

### Backend

1. Install Python 3.10
2. `cd apps/backend-api`
3. `pip install -r requirements.txt`
4. `uvicorn app.main:app --reload --port 8000`

### Frontend

1. Install Node.js LTS
2. `cd apps/frontend-web`
3. `npm install`
4. `npm run dev`

### Collector (Starter)

1. `cd apps/collector-dnp3`
2. Install Python 3.10 and dependencies
3. Run as standalone process or Windows service
