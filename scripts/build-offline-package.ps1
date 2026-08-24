[CmdletBinding()]
param(
  [string]$PythonExe = ".\.venv\Scripts\python.exe",
  [string]$OutputDirectory = "artifacts\\offline-output",
  [switch]$SkipArchive
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$outputRoot = if ([IO.Path]::IsPathRooted($OutputDirectory)) { $OutputDirectory } else { Join-Path $root $OutputDirectory }
$releaseName = "BI-Flow-Mapper-Offline-win-x64"
$stage = Join-Path $outputRoot $releaseName
$zipPath = Join-Path $outputRoot "$releaseName.zip"
$hashPath = "$zipPath.sha256"
$template = Join-Path $root "packaging\offline"
$wheels = Join-Path $stage "wheels"

if (-not (Test-Path -LiteralPath $PythonExe)) {
  throw "Python de build nao encontrado: $PythonExe"
}
& $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32 else 2)"
if ($LASTEXITCODE -ne 0) { throw "O pacote offline deve ser gerado com CPython 3.12 x64." }

if (Test-Path -LiteralPath $stage) {
  throw "Destino ja existe: $stage. Remova-o conscientemente ou escolha -OutputDirectory diferente."
}
if ((Test-Path -LiteralPath $zipPath) -or (Test-Path -LiteralPath $hashPath)) {
  throw "Arquivo de release ja existe em $outputRoot. Escolha outro destino ou remova-o conscientemente."
}

New-Item -ItemType Directory -Path $stage -Force | Out-Null
New-Item -ItemType Directory -Path $wheels -Force | Out-Null

$files = @(
  "backend.py", "bi_server.py", "connector_catalog.py", "connector_matching.py",
  "doc_export.py", "graph_utils.py", "index.html", "launch.ps1", "local_metrics.py",
  "logging_setup.py", "main_app.py", "pbix_analysis.py", "render_graphics.py",
  "tmdl_analysis.py", "styles.css", "requirements.txt", "requirements-runtime.lock",
  "LICENSE"
)
$folders = @("src", "assets", "image")
foreach ($file in $files) { Copy-Item -LiteralPath (Join-Path $root $file) -Destination $stage }
foreach ($folder in $folders) { Copy-Item -LiteralPath (Join-Path $root $folder) -Destination $stage -Recurse }
Copy-Item -LiteralPath (Join-Path $template "Setup-Offline.ps1") -Destination $stage
Copy-Item -LiteralPath (Join-Path $template "Executar.ps1") -Destination $stage
Copy-Item -LiteralPath (Join-Path $template "README-OFFLINE.md") -Destination $stage

# proxy-tools e publicado no indice somente como sdist. Ele e a unica excecao:
# transformamos o sdist em wheel aqui, no computador conectado de build. O
# cliente recebe exclusivamente wheels e nunca compila nem acessa a internet.
$binaryRequirements = @(
  Get-Content -LiteralPath (Join-Path $root "requirements-runtime.lock") |
    Where-Object { $_ -and -not $_.StartsWith("#") -and $_ -notmatch "^proxy-tools==" }
)
& $PythonExe -m pip download --only-binary=:all: --no-deps --dest $wheels @binaryRequirements
if ($LASTEXITCODE -ne 0) { throw "Falha ao baixar wheels binarias para o pacote offline." }
& $PythonExe -m pip wheel --no-deps --wheel-dir $wheels "proxy-tools==0.1.0"
if ($LASTEXITCODE -ne 0) { throw "Falha ao converter proxy-tools em wheel local." }

$wheelCount = @(Get-ChildItem -LiteralPath $wheels -File -Filter "*.whl").Count
if ($wheelCount -lt 1) { throw "Nenhuma wheel foi baixada; o pacote nao e distribuivel offline." }

if (-not $SkipArchive) {
  Compress-Archive -LiteralPath $stage -DestinationPath $zipPath -CompressionLevel Optimal
  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
  Set-Content -LiteralPath $hashPath -Value "$hash  $releaseName.zip" -NoNewline -Encoding ascii
  Write-Host "Pacote criado: $zipPath ($wheelCount wheels)"
  Write-Host "SHA-256: $hashPath"
} else {
  Write-Host "Pasta offline criada: $stage ($wheelCount wheels)"
}
