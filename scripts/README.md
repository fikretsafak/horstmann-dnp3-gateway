# Scripts

PowerShell yardimcilari:

- `install.ps1` - Python 3.10+ venv olusturur, requirements yukler, `.env`
  dosyasi yoksa ornekten kopyalar.
- `run_gateway.ps1` - `.env`'yi yukleyip `py -m dnp3_gateway` calistirir.
  Parametre ile `GATEWAY_CODE`, `GATEWAY_TOKEN`, `WORKER_HEALTH_PORT` override
  edilebilir (ayni makinede birden fazla instance calistirmak icin).

Ust dizinde `run_gateway.cmd` — PowerShell betigi calismazsa (Execution Policy)
`cmd` ile ayni isi yapar: `PYTHONPATH=src` + `python -m dnp3_gateway`.

## "ps1 calismiyor" (sik nedenler)

1. **Execution Policy** — Proje kokunden:
   ```powershell
   Set-Location "...\Horstmann Smart Logger DNP3 Gateway"
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_gateway.ps1
   ```
2. **Profil yok / Path** — Yukaridaki gibi `powershell -File` tam yol ile deneyin.
3. **Betiği çalıştırmak için** Explorer'da `install.ps1`e sağ tık → *PowerShell ile çalıştır* (bazen çalışmaz); en güvenlisi yukarıdaki `Bypass` komutu.

Kurulumdan sonra: `run_gateway.cmd` cift tik veya
`cd` proje + `.venv\Scripts\python.exe -m dnp3_gateway` (`PYTHONPATH` icin
`run_gateway.cmd` kullanin veya `pip install -e .` once).

## Ornekler

```powershell
# Ilk kurulum
./scripts/install.ps1

# Tek gateway (default .env)
./scripts/run_gateway.ps1

# Ayni makinede 2. gateway instance (farkli port + kod)
./scripts/run_gateway.ps1 -GatewayCode GW-002 -GatewayToken gw-002-token -HealthPort 8021
```
