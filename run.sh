#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export OLLAMA_DEFAULT_MODEL="${OLLAMA_DEFAULT_MODEL:-qwen2.5:7b}"
export SYSTEM1_OLLAMA_MODEL="${SYSTEM1_OLLAMA_MODEL:-$OLLAMA_DEFAULT_MODEL}"
export SYSTEM2_OLLAMA_MODEL="${SYSTEM2_OLLAMA_MODEL:-$OLLAMA_DEFAULT_MODEL}"

if command -v ollama >/dev/null 2>&1; then
  if ! ollama list >/dev/null 2>&1; then
    nohup ollama serve > runtime/ollama.log 2>&1 &
    sleep 2
  fi
fi

python3 server.py
