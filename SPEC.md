# SPEC.md — OpenClaw Agent Control Center

> 本文件是项目的核心规格说明。AI Agent 在任何任务开始前必须阅读此文件。

## 1. 项目概述

**项目名称：** OpenClaw Agent Control Center
**类型：** AI Agent 运行时框架 / 多Agent协作系统
**一句话描述：** 让多个AI Agent在同一工作区共享记忆、技能和工具，持续运行、自动工作。
**目标用户：** 追求AI自动化效率的技术用户

## 2. 系统架构

### 2.1 核心组件

| 组件 | 路径 | 职责 |
|------|------|------|
| Gateway | 端口18789 | 会话路由、频道接入、Agent生命周期管理 |
| Agent Runtime | agents/*/ | 各独立Agent的身份、记忆、技能 |
| Memory System | memory/ | 每日日志 + MEMORY.md 长期记忆 |
| Skills | skills/ | 可安装的模块化能力 |
| Workspace | workspace/ | 活跃项目和数据 |

### 2.2 通信流

```
用户 → 渠道(Telegram/WeChat/Discord) → Gateway → Agent
                                                      ↓
                                              Memory/Skills/工具
```

## 3. 功能规格

### 3.1 必须功能（Must Have）

- [x] **多渠道接入** — Telegram/WeChat/Discord
- [x] **文件型记忆系统** — 每日日志 + 长期记忆
- [x] **技能系统** — ClawHub 安装/管理
- [x] **心跳守护** — 主动巡检、周期性任务
- [x] **子Agent派生** — 复杂任务拆分执行
- [x] **Ollama本地模型** — qwen3.5:9b / gemma4:26b
- [x] **语音合成** — edge-tts（晓萱/云希）
- [x] **语音识别** — faster-whisper
- [x] **AI Butler守护进程** — 视觉+语音+大脑模块

### 3.2 待完成功能（In Progress）

- [ ] **摄像头权限** — macOS系统设置授权
- [ ] **GitHub CI/CD** — workflow权限恢复后启用
- [ ] **Nextra文档站托管** — 部署到Vercel/GitHub Pages

### 3.3 规划中功能（Backlog）

- [ ] **MCP服务器集成** — 标准化工具接口
- [ ] **多Agent并行** — 3个以上Agent同时工作
- [ ] **量化交易系统** — 涨停回马枪策略实盘

## 4. 技术约束

- **运行时：** Node.js (Gateway) + Python 3.14 (Agent)
- **本地模型：** Ollama (qwen3.5:9b, gemma4:26b)
- **Python依赖：** faster-whisper, edge-tts, sounddevice, opencv-python
- **启动方式：** LaunchAgent 跟随 Gateway 自动启动
- **端口：** Gateway 18789, Ollama 11434
- **Token：** 不持久化到文件

## 5. 已知问题

| 问题 | 状态 | 解决方案 |
|------|------|----------|
| 摄像头权限 | macOS手动授权 | 系统设置→隐私→摄像头 |
| GitHub workflow scope | 需刷新Token | `gh auth refresh -s workflow` |
| Python 3.14 run_in_executor | 已修复 | 用None作为executor参数 |
| STT离线加载 | 已修复 | `local_files_only=True` |

## 6. 成功标准

- [ ] AI Butler 守护进程稳定运行 > 1小时
- [ ] 语音对讲延迟 < 5秒
- [ ] Gateway 重启后 Agent 自动恢复
- [ ] GitHub 仓库有完整的 CI/CD

---

*最后更新：2026-04-13 by nexu agent*
