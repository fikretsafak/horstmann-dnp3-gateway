$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\..\..\apps\frontend-web"
npm run dev -- --host 0.0.0.0 --port 5173
