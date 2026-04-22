# Service Control Panel (Windows)

Bu panel ile tek ekrandan asagidaki servisleri gorebilir, baslatabilir ve durdurabilirsin:

- PostgreSQL (Windows service)
- RabbitMQ (Windows service)
- Backend API (process)
- Tag Engine Worker (process)
- Alarm Worker (process)
- Outbound Worker (process)
- Frontend Web (process)

## Dosyalar

- `infra/scripts/windows/service_control_panel.py`
- `infra/scripts/windows/service_control_panel.config.json`

## Calistirma

1. `service_control_panel.config.json` icindeki yollari kendi ortamina gore kontrol et.
2. Ozellikle `windows_service_name` alanlari makinandaki servis isimleri ile ayni olmali.
3. Paneli calistir:

```powershell
py -3.10 "infra/scripts/windows/service_control_panel.py"
```

## Notlar

- `Durum` alani:
  - Windows service icin `Get-Service` sonucunu gosterir.
  - Process servisler icin panelin baslattigi process durumunu gosterir.
- `Saglik` alani:
  - Belirtilen host/port icin socket baglantisi ile `UP/DOWN` kontrolu yapar.
- Worker servisleri icin ayri health port kullanilir:
  - Tag Engine Worker: `8011`
  - Alarm Worker: `8012`
  - Outbound Worker: `8013`
- `Log Goster`:
  - Sadece panelin baslattigi process servislerinin canli loglarini gosterir.
  - Windows service loglari Event Viewer tarafindadir.
