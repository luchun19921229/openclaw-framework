"""
大脑模块 — 对话管理、意图识别和决策。

管理多轮对话上下文，调用Ollama聊天模型生成回复，
协调视觉和语音模块完成用户的请求。
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """用户意图枚举。"""
    CHAT = "chat"                  # 普通对话
    DESCRIBE_SCREEN = "describe_screen"  # 描述屏幕
    DESCRIBE_CAMERA = "describe_camera"  # 描述摄像头
    SYSTEM_COMMAND = "system_command"    # 系统命令
    UNKNOWN = "unknown"


@dataclass
class Message:
    """对话消息。"""
    role: str          # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class BrainModule:
    """大脑模块 — 对话管理、意图识别和回复生成。"""

    def __init__(self, config: dict):
        """
        初始化大脑模块。

        Args:
            config: 完整配置字典。
        """
        self._config = config
        brain_cfg = config.get("brain", {})
        ollama_cfg = config.get("ollama", {})

        self._system_prompt = brain_cfg.get("system_prompt", "你是一个有用的AI助手。")
        self._max_history = brain_cfg.get("max_history", 20)
        self._context_timeout = brain_cfg.get("context_timeout", 300)

        self._ollama_url = ollama_cfg.get("base_url", "http://127.0.0.1:11434")
        self._chat_model = ollama_cfg.get("chat_model", "qwen3.5:9b")
        self._timeout = ollama_cfg.get("timeout", 30)

        # 对话历史
        self._history: list[Message] = []
        self._last_interaction: float = 0

    async def start(self) -> None:
        """启动大脑模块。"""
        logger.info("大脑模块已启动")

    async def stop(self) -> None:
        """停止大脑模块。"""
        logger.info("大脑模块已停止")

    # ========================================================================
    # 对话管理
    # ========================================================================

    def _check_context_timeout(self) -> None:
        """检查上下文是否超时，超时则清空历史。"""
        if self._last_interaction > 0:
            elapsed = time.time() - self._last_interaction
            if elapsed > self._context_timeout:
                logger.info(f"上下文超时 ({elapsed:.0f}s)，清空对话历史")
                self._history.clear()

    def add_user_message(self, text: str, metadata: dict | None = None) -> None:
        """
        添加用户消息到历史。

        Args:
            text: 用户说的话。
            metadata: 附加元数据（如来源：voice/camera/screen）。
        """
        self._check_context_timeout()
        self._history.append(Message(
            role="user",
            content=text,
            metadata=metadata or {},
        ))
        self._trim_history()
        self._last_interaction = time.time()

    def add_assistant_message(self, text: str, metadata: dict | None = None) -> None:
        """
        添加助手回复到历史。

        Args:
            text: 回复文本。
            metadata: 附加元数据。
        """
        self._history.append(Message(
            role="assistant",
            content=text,
            metadata=metadata or {},
        ))
        self._trim_history()

    def _trim_history(self) -> None:
        """裁剪对话历史到最大轮数。"""
        if len(self._history) > self._max_history:
            # 保留最近的消息
            self._history = self._history[-self._max_history:]

    def clear_history(self) -> None:
        """清空对话历史。"""
        self._history.clear()
        self._last_interaction = 0
        logger.info("对话历史已清空")

    # ========================================================================
    # 意图识别
    # ========================================================================

    def detect_intent(self, text: str) -> Intent:
        """
        简单关键词意图识别。

        Args:
            text: 用户输入文本。

        Returns:
            识别的意图。
        """
        text_lower = text.lower()

        # 屏幕描述
        screen_keywords = ["屏幕", "在看什么", "屏幕上", "screen", "看到了什么",
                          "在做什么", "现在做什么", "帮我看看"]
        if any(kw in text_lower for kw in screen_keywords):
            return Intent.DESCRIBE_SCREEN

        # 摄像头描述
        camera_keywords = ["摄像头", "相机", "camera", "拍照", "看看周围",
                          "看看外面", "外面有什么"]
        if any(kw in text_lower for kw in camera_keywords):
            return Intent.DESCRIBE_CAMERA

        # 系统命令
        system_keywords = ["停止", "暂停", "继续", "退出", "关闭", "重启",
                          "stop", "pause", "resume", "quit"]
        if any(kw in text_lower for kw in system_keywords):
            return Intent.SYSTEM_COMMAND

        return Intent.CHAT

    # ========================================================================
    # 对话生成
    # ========================================================================

    async def generate_response(
        self,
        user_text: str,
        context: str | None = None,
    ) -> Optional[str]:
        """
        生成对话回复。

        Args:
            user_text: 用户输入。
            context: 额外上下文（如视觉描述）。

        Returns:
            AI回复文本，或None。
        """
        self.add_user_message(user_text)

        # 构建消息列表
        messages = [{"role": "system", "content": self._system_prompt}]

        # 添加额外上下文
        if context:
            messages.append({
                "role": "system",
                "content": f"[当前上下文]: {context}"
            })

        # 添加对话历史
        for msg in self._history:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # 调用Ollama
        reply = await self._call_ollama_chat(messages)

        if reply:
            self.add_assistant_message(reply)

        return reply

    async def generate_with_vision(
        self,
        user_text: str,
        vision_description: str,
    ) -> Optional[str]:
        """
        结合视觉信息生成回复。

        Args:
            user_text: 用户输入。
            vision_description: 视觉模块的描述结果。

        Returns:
            AI回复文本，或None。
        """
        return await self.generate_response(
            user_text,
            context=f"我刚观察了画面，看到了：{vision_description}"
        )

    async def _call_ollama_chat(self, messages: list[dict]) -> Optional[str]:
        """
        调用Ollama聊天API。

        Args:
            messages: OpenAI格式的消息列表。

        Returns:
            AI回复文本，或None。
        """
        payload = {
            "model": self._chat_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1024,
            }
        }

        url = f"{self._ollama_url}/api/chat"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Ollama聊天失败 (HTTP {resp.status}): {error_text}")
                        return None

                    result = await resp.json()
                    reply = result.get("message", {}).get("content", "").strip()
                    if reply:
                        logger.info(f"AI回复: {reply[:100]}...")
                    return reply if reply else None

        except aiohttp.ClientError as e:
            logger.error(f"Ollama连接失败: {e}")
            return None
        except asyncio.TimeoutError:
            logger.error("Ollama聊天超时")
            return None
        except Exception as e:
            logger.error(f"聊天生成出错: {e}")
            return None

    async def generate_summary(self, conversation: list[dict]) -> Optional[str]:
        """
        生成对话摘要（用于同步到Gateway记忆）。

        Args:
            conversation: 对话记录列表。

        Returns:
            摘要文本。
        """
        if not conversation:
            return None

        conv_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else 'AI'}: {m['content']}"
            for m in conversation
        )

        messages = [
            {
                "role": "system",
                "content": "请用2-3句话简要总结以下对话的关键内容，用中文回答。"
            },
            {
                "role": "user",
                "content": conv_text,
            }
        ]

        return await self._call_ollama_chat(messages)

    @property
    def history_messages(self) -> list[Message]:
        """获取当前对话历史（只读）。"""
        return list(self._history)

    @property
    def has_context(self) -> bool:
        """是否有有效的对话上下文。"""
        if not self._history:
            return False
        if self._last_interaction <= 0:
            return False
        return (time.time() - self._last_interaction) < self._context_timeout
