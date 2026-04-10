# AI Butler — macOS 本地 AI 管家系统

一个运行在 MacBook 上的本地 AI 管家，具备**视觉感知**、**语音对话**和**OpenClaw Gateway 集成**能力。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🖥️ **屏幕感知** | 自动捕获屏幕，用视觉模型分析"你在看什么" |
| 📸 **摄像头视觉** | 调用 MacBook 摄像头，描述拍到的画面 |
| 🎤 **实时语音对话** | 持续监听 → VAD检测 → Whisper识别 → Ollama对话 → edge-tts播报 |
| 🔄 **打断支持** | 用户说话时自动打断AI播放 |
| ⚙️ **配置热重载** | 修改 config.yaml 后自动生效，无需重启 |
| 🚀 **开机自启** | LaunchAgent 守护进程，跟随系统启动 |

## 🏗️ 架构

```
┌─────────────────────────────────────────────────┐
│                   main.py                        │
│              (守护进程 + 事件循环)                  │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Vision   │  │ Voice    │  │ Brain        │   │
│  │ Module   │  │ Module   │  │ Module       │   │
│  │          │  │          │  │              │   │
│  │ 摄像头    │  │ 麦克风    │  │ 对话管理     │   │
│  │ 屏幕截取  │  │ VAD      │  │ 意图识别     │   │
│  │ gemma视觉 │  │ Whisper  │  │ qwen对话     │   │
│  └────┬─────┘  │ edge-tts │  └──────┬───────┘   │
│       │        │ afplay   │         │           │
│       │        └────┬─────┘         │           │
│       │             │               │           │
│       └─────────────┴───────────────┘           │
│                     │                            │
│              ┌──────┴───────┐                    │
│              │ Gateway      │                    │
│              │ Bridge       │                    │
│              │              │                    │
│              │ HTTP API     │                    │
│              │ 记忆同步      │                    │
│              └──────────────┘                    │
│                     │                            │
└─────────────────────┼───────────────────────────┘
                      │ HTTP
              ┌───────┴────────┐
              │ OpenClaw       │
              │ Gateway        │
              │ 127.0.0.1:18789│
              └────────────────┘
```

### 数据流

```
用户说话 → sounddevice录音 → VAD检测 → faster-whisper识别
    → 意图识别 → [视觉分析? → Ollama gemma4:26b]
    → Ollama qwen3.5:9b 对话 → edge-tts合成 → afplay播放
    → 记录对话 → Gateway记忆同步
```

## 📦 项目结构

```
ai-butler/
├── config.yaml              # 配置文件（YAML格式）
├── main.py                  # 主入口，守护进程
├── butler/
│   ├── __init__.py
│   ├── config.py            # 配置管理（热重载）
│   ├── vision.py            # 视觉模块（摄像头+屏幕+Ollama视觉）
│   ├── voice.py             # 语音模块（VAD+STT+TTS+播放）
│   ├── brain.py             # 大脑模块（对话+意图识别）
│   └── gateway.py           # OpenClaw Gateway桥接
├── scripts/
│   ├── install.sh           # 安装脚本
│   ├── start.sh             # 启动脚本
│   └── io.openclaw.aibutler.plist  # LaunchAgent
├── requirements.txt
└── README.md
```

## 🚀 快速开始

### 前置条件

- macOS (Apple Silicon 或 Intel)
- Python 3.10+
- [Ollama](https://ollama.ai) 已安装并运行
- FFmpeg

```bash
# 检查/安装前置
brew install ollama ffmpeg

# 拉取所需模型
ollama pull qwen3.5:9b
ollama pull gemma4:26b
```

### 安装

```bash
cd ai-butler
bash scripts/install.sh
```

### 启动

```bash
# 方式1：手动启动
bash scripts/start.sh

# 方式2：调试模式
bash scripts/start.sh --debug

# 方式3：LaunchAgent（开机自启）
launchctl load ~/Library/LaunchAgents/io.openclaw.aibutler.plist
```

### 停止

```bash
# 如果是手动启动，按 Ctrl+C

# 如果是LaunchAgent
launchctl unload ~/Library/LaunchAgents/io.openclaw.aibutler.plist
```

## ⚙️ 配置

配置文件位置：`~/.ai-butler/config.yaml`

### 关键配置项

```yaml
# 语音识别模型（越大越准，但越慢）
voice:
  stt:
    model_size: "small"    # tiny/base/small/medium/large-v3

# TTS语音
voice:
  tts:
    voice: "zh-CN-YunxiNeural"     # 男声
    # voice: "zh-CN-XiaoxiaoNeural"  # 女声

# VAD灵敏度（如果检测不到说话，降低这个值）
voice:
  vad:
    energy_threshold: 0.003   # 越小越灵敏

# 视觉模型
ollama:
  chat_model: "qwen3.5:9b"
  vision_model: "gemma4:26b"
```

修改配置后会**自动生效**（热重载），无需重启。

## 🎯 使用方式

### 语音交互

启动后，对着麦克风说话即可。系统会自动：
1. 检测你说的话（VAD）
2. 识别语音（Whisper）
3. 理解意图并回复

### 语音命令

| 你说 | 系统行为 |
|------|----------|
| "帮我看看屏幕" / "我在看什么" | 捕获屏幕并用AI描述 |
| "看看摄像头" / "外面有什么" | 捕获摄像头并用AI描述 |
| "暂停" | 暂停语音交互 |
| "继续" | 恢复语音交互 |
| "清空历史" | 清空对话上下文 |
| "退出" | 关闭AI管家 |

### 打断

当AI正在说话时，你可以直接开口说话，AI会立即停止播放并聆听。

## 🔧 故障排查

### 麦克风没有反应
```bash
# 检查麦克风权限
# 系统设置 → 隐私与安全性 → 麦克风 → 确保终端/Python有权限

# 检查音频设备
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

### 摄像头不可用
```bash
# 检查摄像头权限
# 系统设置 → 隐私与安全性 → 摄像头 → 确保终端/Python有权限
```

### Ollama连接失败
```bash
# 确保Ollama在运行
ollama serve

# 检查模型是否已拉取
ollama list
```

### STT识别不准确
```yaml
# 使用更大的模型（但更慢）
voice:
  stt:
    model_size: "medium"  # 或 "large-v3"
```

### VAD不灵敏
```yaml
# 降低能量阈值
voice:
  vad:
    energy_threshold: 0.001   # 更灵敏
```

## 📝 日志

```bash
# 实时查看日志
tail -f ~/.ai-butler/logs/ai-butler.log

# 查看LaunchAgent日志
tail -f ~/.ai-butler/logs/launchd-stderr.log
```

## 🔌 与 OpenClaw Gateway 集成

AI Butler 会自动连接本地运行的 OpenClaw Gateway (`127.0.0.1:18789`)：
- 对话记录会同步到 Gateway 的记忆系统
- 支持通过 Gateway 调用 OpenClaw 技能

如果 Gateway 不可用，AI Butler 会以**离线模式**运行，本地功能不受影响。

## 📄 License

MIT
