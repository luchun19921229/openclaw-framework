#!/bin/bash
# =============================================================================
# AI Butler 安装脚本
# 用法: bash scripts/install.sh
# =============================================================================

set -euo pipefail

BUTLER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="$HOME/.ai-butler"
PYTHON="${PYTHON:-python3}"

echo "============================================="
echo "  AI Butler 安装程序"
echo "============================================="
echo ""
echo "安装目录: $BUTLER_DIR"
echo "配置目录: $CONFIG_DIR"
echo ""

# --- 检查Python ---
echo "[1/5] 检查Python环境..."
if ! command -v "$PYTHON" &>/dev/null; then
    echo "错误: 找不到Python ($PYTHON)，请先安装Python 3.10+"
    exit 1
fi
PYTHON_VERSION=$("$PYTHON" --version 2>&1)
echo "  ✓ $PYTHON_VERSION"

# --- 检查Ollama ---
echo "[2/5] 检查Ollama..."
if ! command -v ollama &>/dev/null; then
    echo "  ⚠ Ollama未安装，请手动安装: brew install ollama"
    echo "  然后拉取模型: ollama pull qwen3.5:9b && ollama pull gemma4:26b"
else
    echo "  ✓ Ollama已安装"
    echo "  请确保已拉取所需模型:"
    echo "    ollama pull qwen3.5:9b"
    echo "    ollama pull gemma4:26b"
fi

# --- 检查FFmpeg ---
echo "[3/5] 检查FFmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    echo "  ⚠ FFmpeg未安装，请安装: brew install ffmpeg"
else
    echo "  ✓ FFmpeg已安装"
fi

# --- 创建虚拟环境并安装Python依赖 ---
echo "[4/5] 安装Python依赖..."
if [ ! -d "$BUTLER_DIR/.venv" ]; then
    "$PYTHON" -m venv "$BUTLER_DIR/.venv"
    echo "  ✓ 虚拟环境已创建"
fi
"$BUTLER_DIR/.venv/bin/pip" install --upgrade pip -q
"$BUTLER_DIR/.venv/bin/pip" install -r "$BUTLER_DIR/requirements.txt" -q
echo "  ✓ 依赖安装完成"

# --- 创建配置目录和默认配置 ---
echo "[5/5] 创建配置..."
mkdir -p "$CONFIG_DIR"

# 如果用户目录没有config.yaml，复制默认配置
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp "$BUTLER_DIR/config.yaml" "$CONFIG_DIR/config.yaml"
    echo "  ✓ 已创建默认配置: $CONFIG_DIR/config.yaml"
else
    echo "  - 配置已存在，跳过覆盖"
fi

# --- 创建日志目录 ---
mkdir -p "$CONFIG_DIR/logs"

# --- 安装LaunchAgent ---
echo ""
echo "安装 LaunchAgent（开机自启）..."
PLIST_SRC="$BUTLER_DIR/scripts/io.openclaw.aibutler.plist"
PLIST_DST="$HOME/Library/LaunchAgents/io.openclaw.aibutler.plist"

# 替换plist中的路径占位符
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|BUTLER_DIR|$BUTLER_DIR|g" \
    -e "s|PYTHON_PATH|$BUTLER_DIR/.venv/bin/python3|g" \
    -e "s|USER_HOME|$HOME|g" \
    "$PLIST_SRC" > "$PLIST_DST"
echo "  ✓ 已安装LaunchAgent: $PLIST_DST"

echo ""
echo "============================================="
echo "  安装完成！"
echo "============================================="
echo ""
echo "启动方式:"
echo "  方法1 (手动启动):  bash $BUTLER_DIR/scripts/start.sh"
echo "  方法2 (LaunchAgent): launchctl load $PLIST_DST"
echo ""
echo "管理命令:"
echo "  启动: launchctl load ~/Library/LaunchAgents/io.openclaw.aibutler.plist"
echo "  停止: launchctl unload ~/Library/LaunchAgents/io.openclaw.aibutler.plist"
echo "  查看日志: tail -f $CONFIG_DIR/logs/ai-butler.log"
echo ""
echo "⚠️  首次运行前请确认:"
echo "  1. Ollama正在运行 (ollama serve)"
echo "  2. 模型已拉取 (ollama pull qwen3.5:9b && ollama pull gemma4:26b)"
echo "  3. macOS已授予终端/Python的麦克风和摄像头权限"
echo ""
