#!/bin/bash
# 语音对话系统启动脚本
# Voice Intercom Launcher

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎤 语音对话系统启动器"
echo "======================"

# 检查 Python
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "❌ 未找到 Python，请先安装 Python 3"
    exit 1
fi
echo "✅ Python: $PYTHON ($($PYTHON --version 2>&1))"

# 检查 Ollama
if ! command -v ollama &>/dev/null; then
    echo "❌ 未找到 Ollama，请先安装: brew install ollama"
    exit 1
fi

# 检查 Ollama 是否运行
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "⚠️  Ollama 未运行，正在启动..."
    ollama serve &
    OLLAMA_PID=$!
    echo "   等待 Ollama 启动..."
    for i in $(seq 1 10); do
        if curl -s http://localhost:11434/api/tags &>/dev/null; then
            echo "✅ Ollama 已启动"
            break
        fi
        sleep 1
    done
fi

# 检查依赖
echo "🔍 检查依赖..."
$PYTHON -c "import faster_whisper, sounddevice, requests" 2>/dev/null || {
    echo "⚠️  缺少依赖，正在安装..."
    $PYTHON -m pip install -r requirements.txt
}

# 启动语音对话
echo ""
echo "🚀 启动语音对话系统..."
echo ""
$PYTHON voice_intercom.py
