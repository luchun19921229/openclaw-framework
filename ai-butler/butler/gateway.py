"""
OpenClaw Gateway 桥接模块。

通过HTTP API与OpenClaw Gateway通信：
- 同步对话记录到Gateway记忆系统
- 查询Gateway状态
- 调用Gateway技能
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class ConversationRecord:
    """一条对话记录。"""
    user_text: str
    assistant_text: str
    timestamp: float = field(default_factory=time.time)
    source: str = "voice"    # voice | camera | screen
    metadata: dict = field(default_factory=dict)


class GatewayBridge:
    """OpenClaw Gateway桥接 — 管理与Gateway的通信。"""

    def __init__(self, config: dict):
        """
        初始化Gateway桥接。

        Args:
            config: 完整配置字典。
        """
        self._config = config
        gw_cfg = config.get("gateway", {})

        self._base_url = gw_cfg.get("base_url", "http://127.0.0.1:18789")
        self._sync_enabled = gw_cfg.get("sync_conversations", True)
        self._sync_interval = gw_cfg.get("sync_interval", 60)
        self._api_timeout = gw_cfg.get("api_timeout", 10)

        # 待同步的对话
        self._pending_conversations: list[ConversationRecord] = []
        self._running = False
        self._sync_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """启动Gateway桥接。"""
        if not self._config.get("gateway", {}).get("enabled", True):
            logger.info("Gateway桥接已禁用，跳过启动")
            return

        logger.info(f"正在启动Gateway桥接 -> {self._base_url}")

        # 检查Gateway是否可达
        reachable = await self.check_gateway()
        if not reachable:
            logger.warning("Gateway不可达，将以离线模式运行")
        else:
            logger.info("Gateway连接成功")

        self._running = True

        if self._sync_enabled:
            self._sync_task = asyncio.create_task(self._sync_loop())
            logger.info(f"对话同步已启动 (间隔: {self._sync_interval}s)")

        logger.info("Gateway桥接已启动")

    async def stop(self) -> None:
        """停止Gateway桥接。"""
        logger.info("正在停止Gateway桥接...")
        self._running = False

        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        # 停止前尝试同步剩余对话
        if self._pending_conversations:
            await self._flush_conversations()

        logger.info("Gateway桥接已停止")

    # ========================================================================
    # Gateway通信
    # ========================================================================

    async def check_gateway(self) -> bool:
        """
        检查Gateway是否可达。

        Returns:
            Gateway是否可达。
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def get_gateway_status(self) -> Optional[dict]:
        """
        获取Gateway状态信息。

        Returns:
            状态字典，或None。
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/api/v1/status",
                    timeout=aiohttp.ClientTimeout(total=self._api_timeout),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except Exception as e:
            logger.debug(f"获取Gateway状态失败: {e}")
            return None

    # ========================================================================
    # 对话同步
    # ========================================================================

    def record_conversation(
        self,
        user_text: str,
        assistant_text: str,
        source: str = "voice",
        metadata: dict | None = None,
    ) -> None:
        """
        记录一条对话，等待同步到Gateway。

        Args:
            user_text: 用户说的话。
            assistant_text: AI的回复。
            source: 对话来源 (voice/camera/screen)。
            metadata: 附加元数据。
        """
        self._pending_conversations.append(ConversationRecord(
            user_text=user_text,
            assistant_text=assistant_text,
            source=source,
            metadata=metadata or {},
        ))
        logger.debug(f"已记录对话 (待同步: {len(self._pending_conversations)})")

    async def _flush_conversations(self) -> None:
        """将待同步的对话批量发送到Gateway。"""
        if not self._pending_conversations:
            return

        conversations = self._pending_conversations.copy()
        self._pending_conversations.clear()

        try:
            # 构建同步数据
            messages = []
            for conv in conversations:
                messages.append({
                    "role": "user",
                    "content": conv.user_text,
                    "timestamp": conv.timestamp,
                    "source": conv.source,
                })
                messages.append({
                    "role": "assistant",
                    "content": conv.assistant_text,
                    "timestamp": conv.timestamp,
                    "source": "ai_butler",
                })

            # 发送到Gateway的记忆API
            async with aiohttp.ClientSession() as session:
                payload = {
                    "source": "ai_butler",
                    "messages": messages,
                    "metadata": {
                        "count": len(conversations),
                        "time_range": {
                            "start": conversations[0].timestamp,
                            "end": conversations[-1].timestamp,
                        }
                    }
                }

                async with session.post(
                    f"{self._base_url}/api/v1/memory/ingest",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._api_timeout),
                ) as resp:
                    if resp.status in (200, 201):
                        logger.info(f"已同步 {len(conversations)} 条对话到Gateway")
                    elif resp.status == 404:
                        # Gateway可能没有memory API，只记录debug日志
                        logger.debug("Gateway memory API不可用 (404)")
                    else:
                        logger.warning(f"对话同步失败 (HTTP {resp.status})")
                        # 放回队列重试
                        self._pending_conversations = conversations + self._pending_conversations

        except aiohttp.ClientError as e:
            logger.warning(f"Gateway通信失败，对话暂存: {e}")
            self._pending_conversations = conversations + self._pending_conversations
        except Exception as e:
            logger.error(f"对话同步出错: {e}")

    async def _sync_loop(self) -> None:
        """定时同步对话的后台任务。"""
        while self._running:
            try:
                await asyncio.sleep(self._sync_interval)
                if not self._running:
                    break
                await self._flush_conversations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"同步循环出错: {e}")
                await asyncio.sleep(5)

    # ========================================================================
    # 技能调用
    # ========================================================================

    async def call_skill(self, skill_name: str, params: dict | None = None) -> Optional[dict]:
        """
        调用OpenClaw Gateway的技能。

        Args:
            skill_name: 技能名称。
            params: 技能参数。

        Returns:
            技能执行结果，或None。
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "skill": skill_name,
                    "params": params or {},
                }

                async with session.post(
                    f"{self._base_url}/api/v1/skills/execute",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.warning(f"技能调用失败: {skill_name} (HTTP {resp.status})")
                        return None

        except Exception as e:
            logger.error(f"技能调用出错: {e}")
            return None

    @property
    def pending_count(self) -> int:
        """待同步的对话数量。"""
        return len(self._pending_conversations)
