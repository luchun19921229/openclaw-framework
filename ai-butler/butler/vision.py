"""
视觉模块 — 摄像头捕获、屏幕捕获和视觉分析。

使用 OpenCV 捕获摄像头画面，screencapture 捕获屏幕，
通过 Ollama 视觉模型 (gemma4:26b) 进行场景理解和描述。
"""

import asyncio
import base64
import io
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import aiohttp
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class VisionModule:
    """视觉模块 — 管理摄像头/屏幕捕获和AI视觉分析。"""

    def __init__(self, config: dict):
        """
        初始化视觉模块。

        Args:
            config: 完整配置字典。
        """
        self._config = config
        vision_cfg = config.get("vision", {})
        ollama_cfg = config.get("ollama", {})

        # 摄像头配置
        self._camera_index = vision_cfg.get("camera_index", 0)
        self._camera_width = vision_cfg.get("camera_width", 640)
        self._camera_height = vision_cfg.get("camera_height", 480)

        # 捕获配置
        self._capture_interval = vision_cfg.get("capture_interval", 30)
        self._jpeg_quality = vision_cfg.get("jpeg_quality", 75)
        self._prompt = vision_cfg.get("prompt", "请描述这张图片的内容。")
        self._max_image_tokens = vision_cfg.get("max_image_tokens", 1024)

        # Ollama配置
        self._ollama_url = ollama_cfg.get("base_url", "http://127.0.0.1:11434")
        self._vision_model = ollama_cfg.get("vision_model", "gemma4:26b")
        self._timeout = ollama_cfg.get("timeout", 30)

        # 内部状态
        self._camera: Optional[cv2.VideoCapture] = None
        self._running = False
        self._last_camera_frame: Optional[np.ndarray] = None
        self._auto_capture_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """启动视觉模块（打开摄像头）。"""
        if not self._config.get("vision", {}).get("enabled", True):
            logger.info("视觉模块已禁用，跳过启动")
            return

        logger.info("正在启动视觉模块...")
        self._running = True

        # 在线程池中打开摄像头（避免阻塞事件循环）
        await asyncio.get_event_loop().run_in_executor(None, self._open_camera)

        # 如果配置了自动捕获，启动定时任务
        if self._capture_interval > 0:
            self._auto_capture_task = asyncio.create_task(self._auto_capture_loop())
            logger.info(f"自动屏幕捕获已启动 (间隔: {self._capture_interval}s)")

        logger.info("视觉模块已启动")

    async def stop(self) -> None:
        """停止视觉模块并释放资源。"""
        logger.info("正在停止视觉模块...")
        self._running = False

        if self._auto_capture_task and not self._auto_capture_task.done():
            self._auto_capture_task.cancel()
            try:
                await self._auto_capture_task
            except asyncio.CancelledError:
                pass

        await asyncio.get_event_loop().run_in_executor(None, self._release_camera)
        logger.info("视觉模块已停止")

    def _open_camera(self) -> None:
        """打开摄像头（同步方法，在线程池中调用）。"""
        try:
            self._camera = cv2.VideoCapture(self._camera_index)
            if not self._camera.isOpened():
                logger.warning(f"无法打开摄像头 {self._camera_index}，摄像头功能不可用")
                self._camera = None
                return

            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self._camera_width)
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self._camera_height)
            logger.info(f"摄像头 {self._camera_index} 已打开 "
                        f"({self._camera_width}x{self._camera_height})")
        except Exception as e:
            logger.error(f"打开摄像头时出错: {e}")
            self._camera = None

    def _release_camera(self) -> None:
        """释放摄像头资源（同步方法）。"""
        if self._camera is not None:
            self._camera.release()
            self._camera = None
            logger.info("摄像头已释放")

    def _capture_camera_frame_sync(self) -> Optional[np.ndarray]:
        """
        从摄像头捕获一帧图像（同步）。

        Returns:
            图像帧 (numpy array) 或 None（如果捕获失败）。
        """
        if self._camera is None or not self._camera.isOpened():
            logger.debug("摄像头不可用")
            return None

        ret, frame = self._camera.read()
        if not ret:
            logger.warning("摄像头读取帧失败")
            return None

        self._last_camera_frame = frame
        return frame

    async def capture_camera(self) -> Optional[np.ndarray]:
        """
        从摄像头捕获一帧图像（异步）。

        Returns:
            图像帧 (numpy array) 或 None。
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self._capture_camera_frame_sync
        )

    def _capture_screen_sync(self) -> Optional[bytes]:
        """
        捕获屏幕截图（同步）。

        Returns:
            JPEG编码的图像字节，或None。
        """
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            # 使用screencapture捕获全屏
            result = subprocess.run(
                ["screencapture", "-x", tmp_path],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.error(f"screencapture失败: {result.stderr}")
                return None

            # 读取并编码为JPEG
            img = cv2.imread(tmp_path)
            if img is None:
                logger.error("无法读取截图文件")
                return None

            # 缩小尺寸以节省token
            h, w = img.shape[:2]
            max_dim = 1024
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))

            _, buffer = cv2.imencode(".jpg", img,
                                     [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality])

            # 清理临时文件
            Path(tmp_path).unlink(missing_ok=True)

            return buffer.tobytes()

        except subprocess.TimeoutExpired:
            logger.error("screencapture超时")
            return None
        except Exception as e:
            logger.error(f"屏幕捕获失败: {e}")
            return None

    async def capture_screen(self) -> Optional[bytes]:
        """
        捕获屏幕截图（异步）。

        Returns:
            JPEG编码的图像字节，或None。
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self._capture_screen_sync
        )

    def _frame_to_jpeg(self, frame: np.ndarray) -> Optional[bytes]:
        """
        将OpenCV帧编码为JPEG字节。

        Args:
            frame: OpenCV图像帧。

        Returns:
            JPEG字节，或None。
        """
        try:
            # 缩小尺寸
            h, w = frame.shape[:2]
            max_dim = 1024
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

            _, buffer = cv2.imencode(".jpg", frame,
                                     [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality])
            return buffer.tobytes()
        except Exception as e:
            logger.error(f"帧编码失败: {e}")
            return None

    async def analyze_image(self, image_bytes: bytes, prompt: str | None = None) -> Optional[str]:
        """
        使用Ollama视觉模型分析图像。

        Args:
            image_bytes: JPEG/PNG图像字节。
            prompt: 分析提示词，默认使用配置中的prompt。

        Returns:
            AI生成的图像描述，或None。
        """
        prompt = prompt or self._prompt
        img_b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "model": self._vision_model,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
            "options": {
                "num_predict": self._max_image_tokens,
            }
        }

        url = f"{self._ollama_url}/api/generate"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Ollama视觉分析失败 (HTTP {resp.status}): {error_text}")
                        return None

                    result = await resp.json()
                    return result.get("response", "").strip()

        except aiohttp.ClientError as e:
            logger.error(f"Ollama连接失败: {e}")
            return None
        except asyncio.TimeoutError:
            logger.error("Ollama视觉分析超时")
            return None
        except Exception as e:
            logger.error(f"视觉分析出错: {e}")
            return None

    async def describe_camera(self) -> Optional[str]:
        """
        捕获摄像头画面并进行AI描述。

        Returns:
            AI描述文本，或None。
        """
        frame = await self.capture_camera()
        if frame is None:
            return "摄像头不可用，无法捕获画面"

        jpeg = self._frame_to_jpeg(frame)
        if jpeg is None:
            return "图像编码失败"

        result = await self.analyze_image(jpeg, "请描述摄像头拍到的画面，重点关注：人物、物品、环境、光线。用简洁中文回答。")
        return result

    async def describe_screen(self) -> Optional[str]:
        """
        捕获屏幕并进行AI描述。

        Returns:
            AI描述文本，或None。
        """
        jpeg = await self.capture_screen()
        if jpeg is None:
            return "屏幕捕获失败"

        result = await self.analyze_image(jpeg, "请描述这个屏幕截图的内容，重点关注：当前打开的应用、正在做什么、显示了什么关键信息。用简洁中文回答。")
        return result

    async def _auto_capture_loop(self) -> None:
        """定时自动捕获屏幕并分析的后台任务。"""
        while self._running:
            try:
                await asyncio.sleep(self._capture_interval)
                if not self._running:
                    break
                logger.debug("自动屏幕捕获中...")
                # 不主动做分析，只保持就绪状态。实际分析按需触发。
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"自动捕获循环出错: {e}")
                await asyncio.sleep(5)

    @property
    def is_camera_available(self) -> bool:
        """检查摄像头是否可用。"""
        return self._camera is not None and self._camera.isOpened()

    async def capture_and_analyze(
        self,
        source: str = "screen",
        prompt: str | None = None
    ) -> Optional[str]:
        """
        统一的捕获+分析接口。

        Args:
            source: "camera" 或 "screen"。
            prompt: 自定义分析提示词。

        Returns:
            AI描述文本，或None。
        """
        if source == "camera":
            frame = await self.capture_camera()
            if frame is None:
                return None
            jpeg = self._frame_to_jpeg(frame)
            if jpeg is None:
                return None
            return await self.analyze_image(jpeg, prompt)
        else:
            jpeg = await self.capture_screen()
            if jpeg is None:
                return None
            return await self.analyze_image(jpeg, prompt)
