---
name: repair-skills-index
description: 维修技能索引 — 记录每次维修问题和解决方案
version: 1.0.0
tags: [index, repair, maintenance]
---

# 维修技能索引

> 每次维修后自动生成，积累维修经验，方便未来快速定位问题。

## 使用方法

```bash
# 查看所有维修记录
ls ~/Desktop/skills/repairs/

# 按组件搜索
grep -l "ai-butler" ~/Desktop/skills/repairs/*.md

# 查看最近维修
ls -t ~/Desktop/skills/repairs/ | head -5
```

## 维修记录列表

| 时间 | 组件 | 问题 | 状态 |
|------|------|------|------|
| (暂无记录) | - | - | - |

## 常见问题速查

| 症状 | 可能的组件 | 快速修复命令 |
|------|-----------|-------------|
| Gateway无响应 | openclaw-gateway | `launchctl load ~/Library/LaunchAgents/io.nexu.openclaw.plist` |
| 模型无法加载 | ollama | `pkill -x ollama; ollama serve &` |
| AI Butler无响应 | ai-butler | `bash ~/Desktop/skills/process-guard/guard.sh` |
| 语音识别失败 | faster-whisper | `export HF_HUB_OFFLINE=1` |

---

*最后更新：2026-04-13*
