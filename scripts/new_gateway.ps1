# Yeni gateway instance icin .env dosyasi olusturur.
#
# Kullanim:
#   .\scripts\new_gateway.ps1 -Code GW-007
#   .\scripts\new_gateway.ps1 -Code GW-007 -HealthPort 8027 -BackendUrl http://192.168.1.10:8000/api/v1
#
# Ayni PC'de coklu gateway icin her birine ayri kod + ayri health portu verin;
# ayni RabbitMQ broker'a yayin yapar, backend de aynidir. Cihazlar backend
# tarafinda gateway-koduna atanir (Smart Logger frontend).

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, HelpMessage = "Gateway kodu (orn: GW-007). Backend kayit edilen kodla AYNI olmali.")]
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")]
    [string]$Code,

    [Parameter(HelpMessage = "Health/metrics HTTP portu. 0 = OS rastgele atasin. Bos birakirsaniz Code uzerinden hesaplanir.")]
    [int]$HealthPort = -1,

    [Parameter(HelpMessage = "Backend API base URL (Smart Logger Process Backend).")]
    [string]$BackendUrl = "http://127.0.0.1:8000/api/v1",

    [Parameter(HelpMessage = "RabbitMQ AMQP URL.")]
    [string]$RabbitUrl = "amqp://guest:guest@localhost:5672/",

    [Parameter(HelpMessage = "Ortam: development | staging | production.")]
    [ValidateSet("development", "staging", "production")]
    [string]$Environment = "development",

    [Parameter(HelpMessage = "MAX_PARALLEL_DEVICES varsayilani. Buyuk gateway'lerde 100+ verin.")]
    [int]$MaxParallelDevices = 25,

    [Parameter(HelpMessage = "Cikti dosyasi. Belirtmezseniz .env.<Code>")]
    [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not $OutFile) { $OutFile = ".env.$Code" }

if (Test-Path $OutFile) {
    Write-Error "Cikti dosyasi zaten var: $OutFile  (uzerine yazmaz). Once silin veya -OutFile farkli verin."
    exit 1
}

# Health port: kullanici vermediyse Code'un sonundaki sayidan +8000 hesapla, yoksa 0 (auto)
if ($HealthPort -lt 0) {
    if ($Code -match '(\d+)$') {
        $n = [int]$matches[1]
        $HealthPort = 8020 + $n
    } else {
        $HealthPort = 0
    }
}

# 32 byte rastgele token (production icin yeterli)
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$token = [Convert]::ToBase64String($bytes).Replace("+","-").Replace("/","_").TrimEnd("=")

$envContent = @"
# Bu dosya scripts/new_gateway.ps1 tarafindan uretilmistir. Code: $Code
# ----------------------------------------------------------------------------
# Horstmann SN2 DNP3 Gateway - $Code
# ----------------------------------------------------------------------------

# Kimlik
GATEWAY_CODE=$Code
GATEWAY_TOKEN=$token
GATEWAY_NAME=Horstmann SN2 Gateway $Code

# Ortam
APP_ENVIRONMENT=$Environment

# Coklu gateway: her instance icin ayri state-dir alt dizini kullanmak gerekirse
# GATEWAY_STATE_DIR=.gateway_state\\$Code  seklinde acin. Mevcut implementasyon
# instance dosyasini code-bazli ayirir (.gateway_state\\instance_$Code.id),
# yani ayni dizinde kalmasi sorun olusturmaz.
GATEWAY_STATE_DIR=.gateway_state

# Calisma modu: mock | dnp3
GATEWAY_MODE=dnp3

# Backend API (Smart Logger Process Backend)
BACKEND_API_URL=$BackendUrl
BACKEND_API_VERIFY_SSL=true
# BACKEND_API_CA_PATH=
CONFIG_REFRESH_SEC=30
CONFIG_TIMEOUT_SEC=5

# RabbitMQ (Smart Logger ile ortak broker, exchange=hsl.events)
RABBITMQ_URL=$RabbitUrl
RABBITMQ_EXCHANGE=hsl.events
RABBITMQ_ROUTING_KEY=telemetry.raw_received

# Health HTTP (port=0 -> OS rastgele bos port atar; gercek port log'da gorunur)
WORKER_HEALTH_HOST=127.0.0.1
WORKER_HEALTH_PORT=$HealthPort

# Polling / paralellik
DEFAULT_POLL_INTERVAL_SEC=5
MAX_PARALLEL_DEVICES=$MaxParallelDevices

# DNP3 master parametreleri
DNP3_LOCAL_ADDRESS=1
DNP3_TCP_PORT=20000
DNP3_RESPONSE_TIMEOUT_SEC=8
DNP3_READ_STRATEGY=event_driven
DNP3_EVENT_BASELINE_INTERVAL_SEC=60
DNP3_DISABLE_UNSOLICITED_ON_CONNECT=true
DNP3_LINK_RESET_ON_CONNECT=true

# Loglama
LOG_LEVEL=INFO
LOG_FORMAT=text
"@

Set-Content -Path $OutFile -Value $envContent -Encoding utf8

Write-Host ""
Write-Host "Olusturuldu: $OutFile" -ForegroundColor Green
Write-Host "  GATEWAY_CODE   : $Code"
Write-Host "  HEALTH_PORT    : $HealthPort"
Write-Host "  BACKEND_API_URL: $BackendUrl"
Write-Host "  RABBITMQ_URL   : $RabbitUrl"
Write-Host ""
Write-Host "Sonraki adimlar:" -ForegroundColor Yellow
Write-Host "  1. Smart Logger backend'inde bu kodla yeni gateway kaydi olusturun ve token alanina YUKARIDAKI tokeni yapistirin:"
Write-Host "     $token"
Write-Host "  2. Cihazlari frontend uzerinden bu gateway'e atayin."
Write-Host "  3. Gateway'i baslatin:"
Write-Host "       py -m dnp3_gateway --env-file $OutFile"
Write-Host ""
