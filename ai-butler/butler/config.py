"""
配置管理模块 — 支持YAML配置加载和热重载。

通过watchdog（文件监控）或定时轮询检测配置文件变更，
自动重新加载并通知注册的回调函数。
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, Coroutine

import yaml

logger = logging.getLogger(__name__)

# 默认配置路径
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class Config:
    """配置管理器 — 加载YAML配置，支持热重载。"""

    def __init__(self, config_path: str | Path | None = None):
        """
        初始化配置管理器。

        Args:
            config_path: 配置文件路径，默认为项目根目录的config.yaml
        """
        self._path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._data: dict[str, Any] = {}
        self._last_mtime: float = 0.0
        self._reload_callbacks: list[Callable[[dict], Coroutine]] = []
        self._reload_task: asyncio.Task | None = None
        self.load()

    def load(self) -> dict[str, Any]:
        """
        从磁盘加载配置文件。

        Returns:
            加载的配置字典。

        Raises:
            FileNotFoundError: 配置文件不存在。
            yaml.YAMLError: YAML解析错误。
        """
        if not self._path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self._path}")

        with open(self._path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

        self._last_mtime = self._path.stat().st_mtime
        logger.info(f"已加载配置: {self._path}")
        return self._data

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点分隔的嵌套键。

        Args:
            key: 配置键，支持 "section.subsection.key" 格式。
            default: 默认值。

        Returns:
            配置值或默认值。

        Example:
            >>> config.get("ollama.chat_model")
            'qwen3.5:9b'
        """
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def __getitem__(self, key: str) -> Any:
        """支持字典式访问。"""
        return self.get(key)

    def all(self) -> dict[str, Any]:
        """返回完整配置字典。"""
        return self._data.copy()

    def _has_changed(self) -> bool:
        """检查配置文件是否已修改。"""
        if not self._path.exists():
            return False
        return self._path.stat().st_mtime > self._last_mtime

    async def watch(self, interval: int = 5) -> None:
        """
        启动配置文件监控，检测变更时自动重载。

        Args:
            interval: 检查间隔（秒）。
        """
        logger.info(f"开始监控配置文件变更 (间隔: {interval}s)")
        while True:
            await asyncio.sleep(interval)
            if self._has_changed():
                logger.info("检测到配置文件变更，正在重新加载...")
                old_data = self._data.copy()
                try:
                    self.load()
                    for callback in self._reload_callbacks:
                        try:
                            await callback(self._data)
                        except Exception as e:
                            logger.error(f"配置重载回调执行失败: {e}")
                    logger.info("配置热重载完成")
                except Exception as e:
                    logger.error(f"配置重载失败: {e}，保留旧配置")
                    self._data = old_data
                    self._last_mtime = self._path.stat().st_mtime

    def on_reload(self, callback: Callable[[dict], Coroutine]) -> None:
        """
        注册配置重载回调。

        Args:
            callback: 异步回调函数，接收新配置字典作为参数。
        """
        self._reload_callbacks.append(callback)

    def start_watch(self, interval: int = 5) -> asyncio.Task:
        """
        启动配置监控任务。

        Args:
            interval: 检查间隔（秒）。

        Returns:
            asyncio.Task对象。
        """
        self._reload_task = asyncio.create_task(self.watch(interval))
        return self._reload_task

    def stop_watch(self) -> None:
        """停止配置监控。"""
        if self._reload_task and not self._reload_task.done():
            self._reload_task.cancel()
            logger.info("已停止配置监控")
