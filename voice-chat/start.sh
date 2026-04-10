#!/bin/bash
# OpenClaw Voice Chat — quick start
cd "$(dirname "$0")"

PORT="${1:-3456}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"

echo "🎙️  Starting Voice Chat server on port $PORT..."
echo "    Ollama: $OLLAMA_URL"
echo ""

export OLLAMA_URL
node server.js "$PORT"
