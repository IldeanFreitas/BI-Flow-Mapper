$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $root "launch.ps1"

if (-not (Test-Path -LiteralPath (Join-Path $root ".venv\Scripts\python.exe"))) {
  throw "Ambiente ainda nao preparado. Execute primeiro .\Setup-Offline.ps1."
}

& $launcher
