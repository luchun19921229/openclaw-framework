"""
语音模块 — 实时语音对话系统。

功能：
- 持续监听麦克风，使用能量阈值VAD检测说话
- faster-whisper 语音识别 (STT)
- edge-tts 语音合成 (TTS)
- afplay 音频播放
- 支持打断（用户说话时停止AI播放）
- 可选唤醒词检测
"""

import asyncio
import io
import logging
import subprocess
import tempfile
import time
from collections import deque
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

# ============================================================================
# 类型定义
# ============================================================================
OnSpeechDetected = Callable[[str], asyncio.Future]  # 收到语音文字后的回调
OnPlaybackStart = Callable[[], None]
OnPlaybackEnd = Callable[[], None]


class VoiceModule:
    """语音模块 — 管理语音输入/输出的完整流水线。"""

    def __init__(self, config: dict):
        """
        初始化语音模块。

        Args:
            config: 完整配置字典。
        """
        self._config = config
        voice_cfg = config.get("voice", {})

        # 录音参数
        self._sample_rate = voice_cfg.get("sample_rate", 16000)
        self._channels = voice_cfg.get("channels", 1)
        self._chunk_duration = voice_cfg.get("chunk_duration", 0.5)
        self._chunk_samples = int(self._sample_rate * self._chunk_duration)

        # VAD参数
        vad_cfg = voice_cfg.get("vad", {})
        self._energy_threshold = vad_cfg.get("energy_threshold", 0.003)
        self._silence_timeout = vad_cfg.get("silence_timeout", 1.5)
        self._min_speech_duration = vad_cfg.get("min_speech_duration", 0.3)
        self._pre_speech_buffer_sec = vad_cfg.get("pre_speech_buffer", 0.3)

        # STT参数
        stt_cfg = voice_cfg.get("stt", {})
        self._stt_model_size = stt_cfg.get("model_size", "small")
        self._stt_device = stt_cfg.get("device", "cpu")
        self._stt_compute_type = stt_cfg.get("compute_type", "int8")
        self._stt_language = stt_cfg.get("language", "zh")
        self._stt_beam_size = stt_cfg.get("beam_size", 5)

        # TTS参数
        tts_cfg = voice_cfg.get("tts", {})
        self._tts_voice = tts_cfg.get("voice", "zh-CN-YunxiNeural")
        self._tts_rate = tts_cfg.get("rate", "+0%")
        self._tts_volume = tts_cfg.get("volume", "+0%")

        # 播放参数
        playback_cfg = voice_cfg.get("playback", {})
        self._playback_backend = playback_cfg.get("backend", "afplay")
        self._interrupt_on_speech = playback_cfg.get("interrupt_on_speech", True)

        # 唤醒词
        self._wake_words = voice_cfg.get("wake_words", [])

        # 内部状态
        self._running = False
        self._is_speaking = False          # AI是否在说话（播放中）
        self._is_user_speaking = False     # 用户是否在说话
        self._is_paused = False            # 暂停语音交互
        self._stt_model = None
        self._audio_buffer: deque = deque() # 预语音缓冲
        self._speech_chunks: list[np.ndarray] = []
        self._last_speech_time: float = 0
        self._playback_process: Optional[subprocess.Popen] = None
        self._listen_task: Optional[asyncio.Task] = None

        # 回调
        self._on_speech_detected: Optional[OnSpeechDetected] = None
        self._on_playback_start: Optional[OnPlaybackStart] = None
        self._on_playback_end: Optional[OnPlaybackEnd] = None

    # ========================================================================
    # 生命周期
    # ========================================================================

    async def start(self) -> None:
        """启动语音模块 — 加载STT模型，开始监听。"""
        if not self._config.get("voice", {}).get("enabled", True):
            logger.info("语音模块已禁用，跳过启动")
            return

        logger.info("正在启动语音模块...")

        # 加载STT模型（在线程池中避免阻塞）
        await asyncio.get_event_loop().run_in_executor(None, self._load_stt_model)

        self._running = True
        self._listen_task = asyncio.create_task(self._listen_loop())
        logger.info("语音模块已启动")

    async def stop(self) -> None:
        """停止语音模块 — 停止录音、播放，释放资源。"""
        logger.info("正在停止语音模块...")
        self._running = False

        # 停止播放
        self._stop_playback()

        # 停止监听
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        logger.info("语音模块已停止")

    # ========================================================================
    # STT模型管理
    # ========================================================================

    def _load_stt_model(self) -> None:
        """加载faster-whisper模型（同步，在线程池中调用）。"""
        try:
            import os
            os.environ["HF_HUB_OFFLINE"] = "1"  # 强制离线，只用本地缓存

            from faster_whisper import WhisperModel
            logger.info(f"正在加载STT模型: {self._stt_model_size} "
                        f"(device={self._stt_device}, compute={self._stt_compute_type})")
            self._stt_model = WhisperModel(
                self._stt_model_size,
                device=self._stt_device,
                compute_type=self._stt_compute_type,
                local_files_only=True,
            )
            logger.info("STT模型加载完成")
        except Exception as e:
            logger.error(f"STT模型加载失败: {e}")
            self._stt_model = None

    def _transcribe_sync(self, audio: np.ndarray) -> Optional[str]:
        """
        语音转文字（同步，在线程池中调用）。

        Args:
            audio: float32音频数据，16kHz单声道。

        Returns:
            识别出的文字，或None。
        """
        if self._stt_model is None:
            logger.error("STT模型未加载")
            return None

        try:
            segments, info = self._stt_model.transcribe(
                audio,
                language=self._stt_language,
                beam_size=self._stt_beam_size,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
            )

            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            text = " ".join(text_parts).strip()
            if text:
                logger.info(f"STT结果: {text}")
            return text if text else None

        except Exception as e:
            logger.error(f"STT转写出错: {e}")
            return None

    # ========================================================================
    # VAD (语音活动检测) + 录音循环
    # ========================================================================

    async def _listen_loop(self) -> None:
        """
        持续监听麦克风的主循环。

        使用简单的能量阈值VAD检测语音起止，
        说话结束后将音频发送给STT识别。
        """
        logger.info("开始监听麦克风...")

        # 预语音缓冲区大小（帧数）
        pre_buffer_frames = max(1, int(self._pre_speech_buffer_sec / self._chunk_duration))
        energy_threshold = self._energy_threshold
        silence_frames_needed = max(1, int(self._silence_timeout / self._chunk_duration))
        min_speech_frames = max(1, int(self._min_speech_duration / self._chunk_duration))

        while self._running:
            try:
                # 在线程池中录音一帧
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None, self._record_chunk
                )

                if chunk is None:
                    await asyncio.sleep(0.05)
                    continue

                # 计算能量
                energy = float(np.sqrt(np.mean(chunk ** 2)))

                if not self._is_user_speaking:
                    # --- 待机状态：检测语音开始 ---
                    self._audio_buffer.append(chunk)

                    # 维护预语音缓冲区
                    while len(self._audio_buffer) > pre_buffer_frames:
                        self._audio_buffer.popleft()

                    if energy > energy_threshold:
                        # 检测到语音开始
                        self._is_user_speaking = True
                        self._last_speech_time = time.time()
                        self._speech_chunks = list(self._audio_buffer)  # 包含预缓冲
                        self._silence_count = 0

                        # 如果AI正在播放且允许打断
                        if self._is_speaking and self._interrupt_on_speech:
                            logger.info("检测到用户说话，打断AI播放")
                            self._stop_playback()

                        logger.debug("检测到语音开始")
                else:
                    # --- 说话状态：收集语音 ---
                    self._speech_chunks.append(chunk)
                    self._last_speech_time = time.time()

                    if energy < energy_threshold:
                        self._silence_count = getattr(self, '_silence_count', 0) + 1
                    else:
                        self._silence_count = 0

                    # 静音超时 → 说话结束
                    if self._silence_count >= silence_frames_needed:
                        self._is_user_speaking = False

                        # 检查最短时长
                        speech_duration = len(self._speech_chunks) * self._chunk_duration
                        if speech_duration < self._min_speech_duration:
                            logger.debug(f"语音太短 ({speech_duration:.1f}s)，忽略")
                            self._speech_chunks = []
                            continue

                        # 合并音频并转写
                        full_audio = np.concatenate(self._speech_chunks)
                        self._speech_chunks = []

                        logger.info(f"语音结束，时长: {speech_duration:.1f}s，开始转写...")

                        # 在线程池中STT
                        text = await asyncio.get_event_loop().run_in_executor(
                            None, self._transcribe_sync, full_audio
                        )

                        if text and self._on_speech_detected:
                            try:
                                await self._on_speech_detected(text)
                            except Exception as e:
                                logger.error(f"语音回调执行出错: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监听循环出错: {e}")
                await asyncio.sleep(0.5)

    def _record_chunk(self) -> Optional[np.ndarray]:
        """
        录制一个音频块（同步）。

        Returns:
            float32音频数据，或None。
        """
        try:
            audio = sd.rec(
                self._chunk_samples,
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
            )
            sd.wait()
            return audio.flatten()
        except Exception as e:
            logger.error(f"录音失败: {e}")
            return None

    # ========================================================================
    # TTS + 播放
    # ========================================================================

    async def speak(self, text: str) -> bool:
        """
        将文本转为语音并播放。

        Args:
            text: 要说的文本。

        Returns:
            是否成功播放。
        """
        if not text.strip():
            return False

        logger.info(f"TTS: {text[:80]}...")

        # 使用edge-tts生成音频
        audio_bytes = await self._generate_tts(text)
        if audio_bytes is None:
            return False

        # 播放
        await self._play_audio(audio_bytes)
        return True

    async def _generate_tts(self, text: str) -> Optional[bytes]:
        """
        使用edge-tts生成语音音频。

        Args:
            text: 要合成的文本。

        Returns:
            MP3音频字节，或None。
        """
        try:
            import edge_tts

            communicate = edge_tts.Communicate(
                text,
                voice=self._tts_voice,
                rate=self._tts_rate,
                volume=self._tts_volume,
            )

            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            if not audio_data:
                logger.warning("TTS未生成音频数据")
                return None

            return audio_data

        except Exception as e:
            logger.error(f"TTS生成失败: {e}")
            return None

    async def _play_audio(self, audio_bytes: bytes) -> None:
        """
        播放音频字节。

        优先使用afplay（macOS原生），备选sounddevice。

        Args:
            audio_bytes: MP3音频字节。
        """
        self._is_speaking = True
        if self._on_playback_start:
            self._on_playback_start()

        try:
            if self._playback_backend == "afplay":
                await self._play_with_afplay(audio_bytes)
            else:
                await self._play_with_sounddevice(audio_bytes)
        except Exception as e:
            logger.error(f"音频播放失败: {e}")
        finally:
            self._is_speaking = False
            if self._on_playback_end:
                self._on_playback_end()

    async def _play_with_afplay(self, audio_bytes: bytes) -> None:
        """
        使用afplay播放音频。

        Args:
            audio_bytes: MP3音频字节。
        """
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            proc = await asyncio.create_subprocess_exec(
                "afplay", tmp_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            self._playback_process = proc
            await proc.wait()

            Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"afplay播放失败: {e}")
        finally:
            self._playback_process = None

    async def _play_with_sounddevice(self, audio_bytes: bytes) -> None:
        """
        使用sounddevice播放音频（需要先解码MP3）。

        Args:
            audio_bytes: MP3音频字节。
        """
        try:
            # 用ffmpeg解码MP3为PCM
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-i", "pipe:0", "-f", "s16le", "-ar", "24000", "-ac", "1",
                "pipe:1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            pcm_data, _ = await proc.communicate(input=audio_bytes)

            if pcm_data:
                audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: sd.play(audio_np, 24000, blocking=True)
                )

        except Exception as e:
            logger.error(f"sounddevice播放失败: {e}")

    def _stop_playback(self) -> None:
        """立即停止当前播放。"""
        if self._playback_process and self._playback_process.returncode is None:
            try:
                self._playback_process.kill()
                logger.debug("已终止播放进程")
            except ProcessLookupError:
                pass

        # 也停掉sounddevice
        try:
            sd.stop()
        except Exception:
            pass

        self._is_speaking = False

    # ========================================================================
    # 回调注册
    # ========================================================================

    def on_speech_detected(self, callback: OnSpeechDetected) -> None:
        """
        注册语音识别完成回调。

        Args:
            callback: 异步回调函数，接收识别出的文本。
        """
        self._on_speech_detected = callback

    def on_playback_start(self, callback: OnPlaybackStart) -> None:
        """注册播放开始回调。"""
        self._on_playback_start = callback

    def on_playback_end(self, callback: OnPlaybackEnd) -> None:
        """注册播放结束回调。"""
        self._on_playback_end = callback

    # ========================================================================
    # 属性
    # ========================================================================

    @property
    def is_playing(self) -> bool:
        """AI是否正在说话。"""
        return self._is_speaking

    @property
    def is_user_speaking(self) -> bool:
        """用户是否正在说话。"""
        return self._is_user_speaking

    def pause(self) -> None:
        """暂停语音交互（不停止监听，只是忽略输入）。"""
        self._is_paused = True
        self._stop_playback()
        logger.info("语音交互已暂停")

    def resume(self) -> None:
        """恢复语音交互。"""
        self._is_paused = False
        logger.info("语音交互已恢复")
