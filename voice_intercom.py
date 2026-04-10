#!/usr/bin/env python3
"""
实时语音对话系统 (Voice Intercom)
流程: 麦克风录音 → Whisper语音识别 → Ollama LLM对话 → edge-tts语音合成 → 扬声器播放
"""

import sys
import os
import io
import time
import json
import queue
import signal
import tempfile
import subprocess
import threading

import numpy as np
import sounddevice as sd
import requests

# ──────────────────────── 配置 ────────────────────────

# Whisper 配置
WHISPER_MODEL_SIZE = "small"  # base / small / medium
WHISPER_DEVICE = "cpu"        # cpu (macOS arm64)
WHISPER_COMPUTE_TYPE = "int8" # int8 for speed on CPU

# Ollama 配置
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3.5:9B"   # 默认模型, 可改为 gemma4:26b
OLLAMA_SYSTEM_PROMPT = (
    "你是一个友好、有帮助的AI助手。请用简洁自然的中文回答问题。"
    "回答尽量简短，控制在3句话以内，适合语音对话场景。"
)

# TTS 配置
TTS_VOICE = "zh-CN-YunxiNeural"  # 男声, 可改为 zh-CN-XiaoxiaoNeural (女声)
TTS_RATE = "+0%"                 # 语速: -50% ~ +100%
TTS_VOLUME = "+0%"              # 音量

# 录音配置
SAMPLE_RATE = 16000
CHANNELS = 1
SILENCE_THRESHOLD = 500        # 静音阈值 (RMS)
SILENCE_DURATION = 1.5         # 静音持续多少秒后停止录音 (秒)
MIN_RECORD_DURATION = 0.5      # 最短录音时长 (秒)

# ──────────────────────── 全局状态 ────────────────────────

audio_queue = queue.Queue()
is_recording = False
conversation_history = []
stop_event = threading.Event()

# ──────────────────────── Whisper 初始化 ────────────────────────

def load_whisper():
    """加载 faster-whisper 模型"""
    print(f"🔄 正在加载 Whisper 模型 ({WHISPER_MODEL_SIZE})...")
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        print(f"✅ Whisper 模型加载完成")
        return model
    except Exception as e:
        print(f"❌ Whisper 模型加载失败: {e}")
        sys.exit(1)

# ──────────────────────── 录音 ────────────────────────

def audio_callback(indata, frames, time_info, status):
    """音频回调函数，将音频数据放入队列"""
    if status:
        print(f"⚠️ 音频状态: {status}", file=sys.stderr)
    audio_queue.put(indata.copy())

def record_audio():
    """录音并检测静音自动停止"""
    print("🎙️  开始录音... (说话后自动停止)")
    audio_queue.queue.clear()
    recorded_chunks = []
    silence_start = None
    start_time = time.time()

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16',
        callback=audio_callback,
        blocksize=int(SAMPLE_RATE * 0.1),  # 100ms 块
    )

    with stream:
        while not stop_event.is_set():
            try:
                chunk = audio_queue.get(timeout=0.5)
                recorded_chunks.append(chunk)

                # 计算 RMS 来判断是否有声音
                rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                elapsed = time.time() - start_time

                if rms > SILENCE_THRESHOLD:
                    silence_start = None
                elif elapsed > MIN_RECORD_DURATION:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= SILENCE_DURATION:
                        break

                # 最长录音 30 秒
                if elapsed > 30:
                    break

            except queue.Empty:
                continue

    if not recorded_chunks:
        return None

    audio_data = np.concatenate(recorded_chunks, axis=0)
    duration = len(audio_data) / SAMPLE_RATE
    print(f"📝 录音完成 ({duration:.1f}秒)")
    return audio_data

# ──────────────────────── 语音识别 ────────────────────────

def transcribe(whisper_model, audio_data):
    """使用 Whisper 进行语音识别"""
    # 转为 float32 归一化
    audio_float = audio_data.astype(np.float32) / 32768.0

    print("🔍 正在识别语音...")
    t0 = time.time()
    segments, info = whisper_model.transcribe(
        audio_float,
        language="zh",
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )
    text = "".join(segment.text for segment in segments).strip()
    elapsed = time.time() - t0
    print(f"🔍 识别完成 ({elapsed:.1f}秒): {text}")
    return text

# ──────────────────────── LLM 对话 ────────────────────────

def chat_ollama(user_text):
    """调用 Ollama API 进行对话"""
    conversation_history.append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": OLLAMA_SYSTEM_PROMPT}]
    messages.extend(conversation_history[-10:])  # 保留最近10轮

    print("🤖 AI 正在思考...")
    t0 = time.time()

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 200,  # 限制回复长度
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        reply = data["message"]["content"].strip()

        # 清理 think 标签 (某些模型会加)
        if "<think>" in reply:
            parts = reply.split("</think>")
            if len(parts) > 1:
                reply = parts[-1].strip()
            else:
                reply = reply.replace("<think>", "").strip()

    except requests.ConnectionError:
        reply = "抱歉，无法连接到 Ollama 服务，请确认 Ollama 正在运行。"
    except Exception as e:
        reply = f"抱歉，对话出错了: {e}"

    elapsed = time.time() - t0
    conversation_history.append({"role": "assistant", "content": reply})
    print(f"🤖 AI 回复 ({elapsed:.1f}秒): {reply}")
    return reply

# ──────────────────────── 语音合成 ────────────────────────

def text_to_speech(text):
    """使用 edge-tts 将文本转为语音并播放"""
    if not text:
        return

    print("🔊 正在合成语音...")
    t0 = time.time()

    try:
        # 使用 edge-tts 命令行生成音频到临时文件
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        result = subprocess.run(
            [
                "edge-tts",
                "--voice", TTS_VOICE,
                "--rate", TTS_RATE,
                "--volume", TTS_VOLUME,
                "--text", text,
                "--write-media", tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            print(f"❌ TTS 合成失败: {result.stderr}")
            return

        elapsed = time.time() - t0
        print(f"🔊 合成完成 ({elapsed:.1f}秒), 正在播放...")

        # 用 afplay 播放 (macOS 原生)
        subprocess.run(["afplay", tmp_path], timeout=30)

        # 清理临时文件
        os.unlink(tmp_path)

    except Exception as e:
        print(f"❌ 语音合成/播放出错: {e}")

# ──────────────────────── 主循环 ────────────────────────

def main():
    print("=" * 50)
    print("🎤 实时语音对话系统 (Voice Intercom)")
    print("=" * 50)
    print(f"  Whisper 模型: {WHISPER_MODEL_SIZE}")
    print(f"  LLM 模型: {OLLAMA_MODEL}")
    print(f"  TTS 语音: {TTS_VOICE}")
    print("=" * 50)
    print()

    # 检查 Ollama 连接
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        if OLLAMA_MODEL not in models and not any(OLLAMA_MODEL.split(":")[0] in m for m in models):
            print(f"⚠️  模型 {OLLAMA_MODEL} 未找到，可用模型: {models}")
            print(f"   请运行: ollama pull {OLLAMA_MODEL}")
            sys.exit(1)
        print(f"✅ Ollama 连接成功，模型 {OLLAMA_MODEL} 可用")
    except requests.ConnectionError:
        print("❌ 无法连接 Ollama，请先运行: ollama serve")
        sys.exit(1)

    # 加载 Whisper
    whisper_model = load_whisper()

    # 播放欢迎语
    text_to_speech("你好，我是语音助手，开始对话吧！")

    print()
    print("💡 使用说明:")
    print("  - 对着麦克风说话，系统会自动检测你的语音")
    print("  - 停止说话后会自动处理")
    print("  - 按 Ctrl+C 退出")
    print()

    def signal_handler(sig, frame):
        print("\n👋 再见！")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # 主对话循环
    while not stop_event.is_set():
        try:
            # 录音
            audio_data = record_audio()
            if audio_data is None:
                continue

            # 语音识别
            text = transcribe(whisper_model, audio_data)
            if not text:
                print("⚠️  未识别到内容，请重试")
                continue

            # 检查退出指令
            if text in ("退出", "结束", "拜拜", "再见", "停止", "quit", "exit", "stop"):
                text_to_speech("再见，期待下次对话！")
                break

            # LLM 对话
            reply = chat_ollama(text)

            # 语音合成 + 播放
            text_to_speech(reply)

            print()
            print("-" * 40)
            print()

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")
            continue

if __name__ == "__main__":
    main()
