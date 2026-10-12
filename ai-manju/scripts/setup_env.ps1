$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot

if (-not $env:HF_ENDPOINT) {
  $env:HF_ENDPOINT = "https://hf-mirror.com"
}

$Directories = @(
  "$RootDir\data\novel_index",
  "$RootDir\models",
  "$RootDir\uploads\frames",
  "$RootDir\uploads\videos",
  "$RootDir\uploads\audio",
  "$RootDir\output",
  "$RootDir\logs"
)

foreach ($Dir in $Directories) {
  New-Item -ItemType Directory -Force -Path $Dir | Out-Null
}

Write-Host "HF_ENDPOINT=$($env:HF_ENDPOINT)"
Write-Host "项目目录已初始化: $RootDir"
Write-Host "下一步可执行:"
Write-Host "  python -m venv .venv"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  pip install -r requirements.txt"
Write-Host "  python scripts/validate_ref2va_env.py"
Write-Host "  python scripts/download_models.py --only ref2va_bundle"
