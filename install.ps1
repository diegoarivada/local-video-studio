# Windows setup: virtual env, PyTorch (CUDA if you have an NVIDIA GPU), Python packages, and the script model.
# Run from the repo folder:  powershell -ExecutionPolicy Bypass -File install.ps1  [-Cpu] [-Model qwen3:8b]
param([switch]$Cpu, [string]$Model = "qwen3:8b")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Python 3.14: on older Pythons Chatterbox pins torch 2.6, which would replace the GPU build and doesn't support RTX 50-series.
if (-not (Test-Path .venv)) {
    py -3.14 -m venv .venv
    if ($LASTEXITCODE) { Write-Host "Install Python 3.14 from python.org (or: winget install Python.Python.3.14), then re-run." -ForegroundColor Red; exit 1 }
}
$py = ".venv\Scripts\python.exe"
& $py -m pip install -q --upgrade pip

if ($Cpu) {
    & $py -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
} else {
    # CUDA 13 wheels cover RTX 20-series through 50-series. Use -Cpu if you don't have an NVIDIA GPU.
    & $py -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130
}
& $py -m pip install -r requirements.txt
& $py -m pip install -q --no-deps -r requirements-overrides.txt   # patched versions, see the file

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Install Ollama from https://ollama.com/download, then run: ollama pull $Model" -ForegroundColor Yellow
} else {
    ollama pull $Model
}
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "`nReady. Add your free Pixabay key to .env, then:" -ForegroundColor Green
Write-Host "  .venv\Scripts\python -m studio make `"Why you should back up your photos`" --minutes 3"
