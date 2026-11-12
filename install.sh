#!/usr/bin/env bash
# macOS / Linux setup: virtual env, PyTorch, Python packages, and the script model.
# Run from the repo folder:  ./install.sh [model]
set -euo pipefail
cd "$(dirname "$0")"
MODEL="${1:-qwen3:8b}"

# Python 3.14: on older Pythons Chatterbox pins torch 2.6, which would replace the GPU build.
if [ ! -d .venv ]; then
  command -v python3.14 >/dev/null 2>&1 || { echo "Install Python 3.14 first (python.org, brew install python@3.14, or your distro)."; exit 1; }
  python3.14 -m venv .venv
fi
PY=.venv/bin/python
$PY -m pip install -q --upgrade pip
if command -v nvidia-smi >/dev/null 2>&1; then
  $PY -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130
else
  $PY -m pip install torch torchaudio   # CPU on Linux, Metal (mps) on Apple Silicon
fi
$PY -m pip install -r requirements.txt
$PY -m pip install -q --no-deps -r requirements-overrides.txt   # patched versions, see the file

if command -v ollama >/dev/null 2>&1; then ollama pull "$MODEL"; else
  echo "Install Ollama from https://ollama.com/download, then run: ollama pull $MODEL"; fi
[ -f .env ] || cp .env.example .env
echo
echo "Ready. Add your free Pixabay key to .env, then:"
echo "  .venv/bin/python -m studio make \"Why you should back up your photos\" --minutes 3"
