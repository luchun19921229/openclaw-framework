#!/bin/bash
# =============================================================================
# AI Butler 启动脚本
# 用法: bash scripts/start.sh [--debug] [--config /path/to/config.yaml]
# =============================================================================

set -euo pipefail

BUTLER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="$HOME/.ai-butler"
PYTHON="${PYTHON:-python3}"

# 默认参数
LOG_LEVEL="INFO"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
EXTRA_ARGS=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --debug|-d)
            LOG_LEVEL="DEBUG"
            shift
            ;;
        --config|-c)
            CONFIG_FILE="$2"
            shift 2
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

echo "============================================="
echo "  AI Butler 启动中..."
echo "  日志级别: $LOG_LEVEL"
echo "  配置文件: $CONFIG_FILE"
echo "============================================="
echo ""

# 检查Ollama是否运行
if ! curl -s http://127.0.0.1:11434/api/tags &>/dev/null; then
    echo "⚠️  Ollama似乎没有运行，正在尝试启动..."
    ollama serve &
    sleep 2
fi

# 启动AI Butler
cd "$BUTLER_DIR"
exec "$PYTHON" main.py \
    --config "$CONFIG_FILE" \
    --log-file "$CONFIG_DIR/logs/ai-butler.log" \
    --verbose "$LOG_LEVEL" \
    $EXTRA_ARGS
