#!/bin/bash
#===============================================================================
# OpenClaw & nexu 互相守护脚本
# 每小时自动执行，检查对方进程是否正常
#===============================================================================

LOG_FILE="$HOME/Desktop/skills/process-guard/guard.log"
SKILL_DIR="$HOME/Desktop/skills/repairs"
STATE_FILE="$HOME/.openclaw/process-guard/state.json"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查OpenClaw Gateway
check_openclaw_gateway() {
    log "检查 OpenClaw Gateway..."
    if curl -s --max-time 5 http://127.0.0.1:18789 > /dev/null 2>&1; then
        log "${GREEN}✓${NC} OpenClaw Gateway 运行正常"
        return 0
    else
        log "${RED}✗${NC} OpenClaw Gateway 未响应"
        return 1
    fi
}

# 检查Ollama
check_ollama() {
    log "检查 Ollama..."
    if curl -s --max-time 5 http://127.0.0.1:11434 > /dev/null 2>&1; then
        log "${GREEN}✓${NC} Ollama 运行正常"
        return 0
    else
        log "${RED}✗${NC} Ollama 未响应"
        return 1
    fi
}

# 检查AI Butler守护进程
check_ai_butler() {
    log "检查 AI Butler..."
    if pgrep -f "main.py.*ai-butler" > /dev/null 2>&1; then
        log "${GREEN}✓${NC} AI Butler 运行正常"
        return 0
    else
        log "${RED}✗${NC} AI Butler 未运行"
        return 1
    fi
}

# 检查nexu agent
check_nexu() {
    log "检查 nexu agent..."
    if curl -s --max-time 5 http://127.0.0.1:18789 > /dev/null 2>&1; then
        log "${GREEN}✓${NC} nexu Gateway 运行正常"
        return 0
    else
        log "${RED}✗${NC} nexu Gateway 未响应"
        return 1
    fi
}

# 生成维修报告（skill格式）
write_repair_skill() {
    local issue="$1"
    local action="$2"
    local component="$3"
    local timestamp=$(date '+%Y-%m-%d_%H%M%S')
    local skill_file="$SKILL_DIR/repair_${component}_${timestamp}.md"
    
    cat > "$skill_file" << EOF
---
name: repair-${component}-${timestamp}
description: 修复记录 - ${issue}
version: 1.0.0
component: ${component}
tags: [repair, maintenance, ${component}]
created: ${timestamp}
---

# 维修记录

## 问题
${issue}

## 维修操作
${action}

## 时间
${timestamp}

## 组件
${component}

## 状态
已修复

---
EOF
    log "已保存维修记录: $skill_file"
}

# 修复OpenClaw Gateway
fix_openclaw_gateway() {
    log "${YELLOW}→ 尝试修复 OpenClaw Gateway...${NC}"
    log "1. 检查LaunchAgent状态..."
    launchctl list | grep -i openclaw | head -3
    
    log "2. 尝试重启Gateway..."
    if [ -f /Users/mr.lcccc/.nexu/runtime/nexu-runner.app/Contents/MacOS/Nexu ]; then
        /Users/mr.lcccc/.nexu/runtime/nexu-runner.app/Contents/MacOS/Nexu \
            /Users/mr.lcccc/.nexu/openclaw-sidecar/node_modules/openclaw/openclaw.mjs \
            gateway run --port 18789 &
        sleep 3
        if curl -s --max-time 5 http://127.0.0.1:18789 > /dev/null 2>&1; then
            log "${GREEN}✓${NC} OpenClaw Gateway 修复成功！"
            write_repair_skill "OpenClaw Gateway停止响应" "重启Gateway进程，端口18789" "openclaw-gateway"
            return 0
        fi
    fi
    
    log "${RED}✗${NC} OpenClaw Gateway 修复失败"
    write_repair_skill "OpenClaw Gateway停止响应，尝试重启失败" "需要人工介入检查" "openclaw-gateway"
    return 1
}

# 修复Ollama
fix_ollama() {
    log "${YELLOW}→ 尝试修复 Ollama...${NC}"
    
    log "1. 检查Ollama进程..."
    if pgrep -x ollama > /dev/null 2>&1; then
        log "Ollama进程存在，尝试重启..."
        pkill -x ollama 2>/dev/null
        sleep 2
    fi
    
    log "2. 启动Ollama..."
    ollama serve &
    sleep 5
    
    if curl -s --max-time 5 http://127.0.0.1:11434 > /dev/null 2>&1; then
        log "${GREEN}✓${NC} Ollama 修复成功！"
        write_repair_skill "Ollama服务停止" "杀死旧进程，重新启动ollama serve" "ollama"
        return 0
    fi
    
    log "${RED}✗${NC} Ollama 修复失败"
    write_repair_skill "Ollama服务停止，重启失败" "需要人工介入检查" "ollama"
    return 1
}

# 修复AI Butler
fix_ai_butler() {
    log "${YELLOW}→ 尝试修复 AI Butler...${NC}"
    
    # 找到venv路径
    VENV_PATH="$HOME/openclaw-oss/ai-butler/.venv/bin/python3"
    MAIN_PATH="$HOME/openclaw-oss/ai-butler/main.py"
    CONFIG_PATH="$HOME/.ai-butler/config.yaml"
    
    if [ ! -f "$MAIN_PATH" ]; then
        log "${RED}✗${NC} AI Butler 主程序不存在，尝试重建..."
        write_repair_skill "AI Butler主程序缺失" "需要重新创建AI Butler" "ai-butler"
        return 1
    fi
    
    log "1. 杀掉旧进程..."
    pkill -f "main.py.*ai-butler" 2>/dev/null
    sleep 2
    
    log "2. 重新启动AI Butler..."
    export OPENCV_AVFOUNDATION_SKIP_AUTH=1
    export HF_HUB_OFFLINE=1
    nohup "$VENV_PATH" "$MAIN_PATH" --config "$CONFIG_PATH" >> "$HOME/.ai-butler/ai-butler.log" 2>&1 &
    sleep 5
    
    if pgrep -f "main.py.*ai-butler" > /dev/null 2>&1; then
        log "${GREEN}✓${NC} AI Butler 修复成功！"
        write_repair_skill "AI Butler守护进程停止" "杀死旧进程，重新启动main.py" "ai-butler"
        return 0
    fi
    
    log "${RED}✗${NC} AI Butler 修复失败，查看日志:"
    tail -5 "$HOME/.ai-butler/ai-butler.log" 2>/dev/null
    write_repair_skill "AI Butler守护进程停止，重启失败" "需要检查venv路径和依赖" "ai-butler"
    return 1
}

# 生成检查报告
generate_report() {
    local gw=$1; local oll=$2; local butler=$3; local nexu=$4
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    cat > "$STATE_FILE" << EOF
{
  "last_check": "$timestamp",
  "openclaw_gateway": $gw,
  "ollama": $oll,
  "ai_butler": $butler,
  "nexu": $nexu,
  "all_healthy": $([ $gw -eq 0 ] && [ $oll -eq 0 ] && [ $butler -eq 0 ] && [ $nexu -eq 0 ] && echo "true" || echo "false")
}
EOF
}

#===============================================================================
# 主流程
#===============================================================================
main() {
    log "=========================================="
    log "  互相守护检查开始 $(date '+%Y-%m-%d %H:%M')"
    log "=========================================="
    
    local gw_status=0 oll_status=0 butler_status=0 nexu_status=0
    
    # 检查各组件
    check_openclaw_gateway || { fix_openclaw_gateway; gw_status=$?; }
    check_ollama || { fix_ollama; oll_status=$?; }
    check_ai_butler || { fix_ai_butler; butler_status=$?; }
    check_nexu || nexu_status=1
    
    # 生成状态报告
    generate_report $gw_status $oll_status $butler_status $nexu_status
    
    local all_ok=$(( ! gw_status && ! oll_status && ! butler_status && ! nexu_status ))
    
    log "=========================================="
    if [ $all_ok -eq 1 ]; then
        log "  ✓ 全部正常"
    else
        log "  ⚠ 有组件异常，已尝试修复"
    fi
    log "=========================================="
}

main "$@"
