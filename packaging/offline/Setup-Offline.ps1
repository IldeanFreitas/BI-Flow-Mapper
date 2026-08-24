[CmdletBinding()]
param(
  [string]$PythonExe = "python.exe"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$lockFile = Join-Path $root "requirements-runtime.lock"
$wheels = Join-Path $root "wheels"

if (-not (Test-Path -LiteralPath $lockFile) -or -not (Test-Path -LiteralPath $wheels)) {
  throw "Pacote offline incompleto: requirements-runtime.lock ou wheels nao foi encontrado."
}

if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
  throw "Python nao encontrado em '$PythonExe'. Instale o CPython 3.12 ou informe -PythonExe <caminho>."
}

& $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 2)"
if ($LASTEXITCODE -ne 0) {
  throw "Este pacote exige CPython 3.12 de 64 bits."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
  & $PythonExe -m venv (Join-Path $root ".venv")
  if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente virtual local." }
}

& $venvPython -m pip install --no-index --no-input --disable-pip-version-check --find-links $wheels --requirement $lockFile
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependencias usando somente as wheels locais." }

& $venvPython -c "import pbixray, docx, PIL, webview; print('Ambiente offline pronto.')"
if ($LASTEXITCODE -ne 0) { throw "A validacao das dependencias instaladas falhou." }

Write-Host "Concluido. Execute .\Executar.ps1 ou abra esta pasta no VS Code."
