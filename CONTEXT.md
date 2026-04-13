# CONTEXT.md — OpenClaw 项目状态

> 本文件是 GSD 风格的任务上下文。每次任务开始前读取，保持上下文连贯。

## 当前阶段：🏃 活跃执行

**更新时间：** 2026-04-13

---

## 📌 进行中的任务

### 1. OpenClaw OSS 仓库（优先级：高）
- **状态：** GitHub 已推送 ✅
- **链接：** https://github.com/luchun19921229/openclaw-framework
- **待完成：** 
  - [ ] GitHub workflow 权限恢复 (`gh auth refresh -s workflow`)
  - [ ] Nextra 文档站部署到 Vercel

### 2. AI Butler 守护进程（优先级：高）
- **状态：** 核心功能正常运行 ⚠️
- **卡点：** 摄像头需要 macOS 系统授权
- **解决方案：** 用户在 系统设置→隐私→摄像头 开启终端权限

### 3. GSD 框架集成（优先级：高）⭐ NEW
- **状态：** 刚安装完成 v1.34.2
- **路径：** `~/.config/opencode/`
- **关键Agent：** planner/verifier/executor/roadmapper
- **目标：** 将 GSD 的上下文工程融入 OpenClaw 工作流

---

## 🔒 已锁定的决策（不可修改）

1. 使用 Ollama 本地模型，不依赖云API（成本考虑）
2. AI Butler 用 edge-tts 语音合成，不用 ElevenLabs
3. 记忆系统用文件型，不用数据库（简单、可靠）
4. 不使用 pyaudio，用 sounddevice（macOS兼容）

---

## 📊 系统状态

| 组件 | 状态 | 备注 |
|------|------|------|
| OpenClaw Gateway | ✅ 运行中 | 端口 18789 |
| Ollama | ✅ 运行中 | qwen3.5:9b / gemma4:26b |
| GSD v1.34.2 | ✅ 已安装 | 24个Agent |
| AI Butler | ✅ 运行中 | 语音✅ 视觉⚠️ |
| Nextra 文档 | ✅ 已搭建 | 待部署 |
| GitHub 仓库 | ✅ 已推送 | openclaw-framework |

---

## 🔄 多Agent互相守护系统 ⭐ NEW

### 架构

```
nexu agent ←───── 互相守护 ─────→ OpenClaw
   │                                        │
   ├── 定时检查 (每小时)                     ├── 定时检查 (每小时)
   │    • Gateway健康                      │    • Gateway健康
   │    • Ollama服务                      │    • Ollama服务
   │    • AI Butler进程                  │    • AI Butler进程
   │    • 各自进程状态                    │    • 各自进程状态
   │                                        │
   └── 异常时自动修复 ──────────────────────┘

维修记录 → ~/Desktop/skills/repairs/
```

### 守护脚本
- **路径:** `~/Desktop/skills/process-guard/guard.sh`
- **执行:** 定时任务每小时运行一次
- **检查组件:** OpenClaw Gateway / Ollama / AI Butler / nexu
- **自动修复:** 检测到异常立即尝试修复

### 维修记录
- **索引:** `~/Desktop/skills/repairs/SKILL.md`
- **记录文件:** `~/Desktop/skills/repairs/repair_组件_时间戳.md`
- **格式:** SKILL.md格式，包含问题/操作/时间/状态

### 定时任务
| 任务 | 时间 | 触发 |
|------|------|------|
| 基金C+B方案早盘推送 | 每天08:00 | Cron |
| 互相守护检查 | 每小时:00 | Cron ✅ 新增 |

---

## 🎯 下一步行动（按优先级）

1. **【用户操作】** 在 macOS 系统设置里授权摄像头 → 完成后测试 AI Butler 视觉
2. **【用户操作】** `gh auth refresh -s workflow` → 恢复 CI/CD
3. **【自动】** 部署 Nextra 到 Vercel（`npm run build` 后推送）
4. **【研究】** 将 GSD 的 SPEC→CONTEXT→PLAN 流程整合到 OpenClaw 的 agent 启动流程

---

## 🔗 资源链接

- GitHub: https://github.com/luchun19921229/openclaw-framework
- GSD Docs: `~/.config/opencode/commands/get-shit-done/`
- AI Butler: `~/Desktop/openclaw-oss/ai-butler/`
