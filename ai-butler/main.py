"""
AI Butler 主入口 — 守护进程模式运行。

协调所有模块（视觉、语音、大脑、Gateway桥接），
处理信号，管理生命周期。
"""

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from butler.config import Config
from butler.vision import VisionModule
from butler.voice import VoiceModule
from butler.brain import BrainModule, Intent
from butler.gateway import GatewayBridge

# ============================================================================
# 日志配置
# ============================================================================

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """
    配置日志系统。

    Args:
        log_level: 日志级别。
        log_file: 日志文件路径，None则只输出到控制台。
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=handlers,
    )

    # 降低aiohttp等库的日志级别
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# ============================================================================
# PID文件管理
# ============================================================================

def write_pid(pid_file: str) -> None:
    """写入PID文件。"""
    path = Path(pid_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()))


def remove_pid(pid_file: str) -> None:
    """删除PID文件。"""
    Path(pid_file).unlink(missing_ok=True)


def check_pid(pid_file: str) -> bool:
    """
    检查是否已有实例在运行。

    Returns:
        是否有运行中的实例。
    """
    path = Path(pid_file)
    if not path.exists():
        return False

    try:
        pid = int(path.read_text().strip())
        # 检查进程是否存在
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        # PID无效或进程不存在，清理旧文件
        path.unlink(missing_ok=True)
        return False


# ============================================================================
# AI Butler 守护进程
# ============================================================================

class AIButler:
    """AI管家主类 — 管理所有模块的生命周期和交互逻辑。"""

    def __init__(self, config_path: str | None = None):
        """
        初始化AI管家。

        Args:
            config_path: 配置文件路径，None则使用默认路径。
        """
        self.config = Config(config_path)
        self._running = False

        # 初始化模块
        self.vision = VisionModule(self.config.all())
        self.voice = VoiceModule(self.config.all())
        self.brain = BrainModule(self.config.all())
        self.gateway = GatewayBridge(self.config.all())

        # 注册回调
        self.voice.on_speech_detected(self._handle_speech)
        self.voice.on_playback_start(self._on_ai_speaking)
        self.voice.on_playback_end(self._on_ai_done_speaking)

        # 注册配置热重载回调
        self.config.on_reload(self._on_config_reload)

        self._logger = logging.getLogger("butler")

    async def _on_config_reload(self, new_config: dict) -> None:
        """
        配置热重载回调 — 更新各模块的配置。

        Args:
            new_config: 新配置字典。
        """
        self._logger.info("应用新配置...")
        self.vision._config = new_config
        self.voice._config = new_config
        self.brain._config = new_config
        self.gateway._config = new_config
        # 注意：部分参数（如STT模型）需要重启才能生效

    async def start(self) -> None:
        """启动所有模块。"""
        self._logger.info("=" * 60)
        self._logger.info("  AI Butler 正在启动...")
        self._logger.info("=" * 60)

        self._running = True

        # 启动配置热重载
        reload_interval = self.config.get("general.config_reload_interval", 5)
        self.config.start_watch(reload_interval)

        # 启动各模块
        await self.brain.start()
        await self.gateway.start()
        await self.vision.start()
        await self.voice.start()

        self._logger.info("=" * 60)
        self._logger.info("  AI Butler 启动完成！")
        self._logger.info("  对着麦克风说话即可开始对话")
        self._logger.info("  按 Ctrl+C 退出")
        self._logger.info("=" * 60)

    async def stop(self) -> None:
        """停止所有模块并清理资源。"""
        self._logger.info("AI Butler 正在关闭...")
        self._running = False

        # 停止顺序：voice → vision → gateway → brain
        await self.voice.stop()
        await self.vision.stop()
        await self.gateway.stop()
        await self.brain.stop()

        # 停止配置监控
        self.config.stop_watch()

        self._logger.info("AI Butler 已关闭")

    # ========================================================================
    # 交互逻辑
    # ========================================================================

    async def _handle_speech(self, text: str) -> None:
        """
        处理用户语音输入的回调。

        这是整个系统的核心交互入口：
        1. 识别用户意图
        2. 根据意图执行操作（视觉分析/对话）
        3. 生成回复
        4. 语音播报
        5. 同步到Gateway

        Args:
            text: STT识别出的用户语音文本。
        """
        self._logger.info(f"用户说: {text}")

        # 意图识别
        intent = self.brain.detect_intent(text)
        self._logger.info(f"识别意图: {intent.value}")

        reply = None

        if intent == Intent.DESCRIBE_SCREEN:
            # 用户要看屏幕
            reply = await self._handle_describe_screen(text)

        elif intent == Intent.DESCRIBE_CAMERA:
            # 用户要看摄像头
            reply = await self._handle_describe_camera(text)

        elif intent == Intent.SYSTEM_COMMAND:
            # 系统命令
            reply = await self._handle_system_command(text)

        else:
            # 普通对话
            reply = await self._handle_chat(text)

        # 语音播报
        if reply:
            await self.voice.speak(reply)

            # 记录到Gateway
            self.gateway.record_conversation(
                user_text=text,
                assistant_text=reply,
                source="voice",
            )

    async def _handle_chat(self, text: str) -> str | None:
        """
        处理普通对话。

        Args:
            text: 用户输入。

        Returns:
            AI回复。
        """
        return await self.brain.generate_response(text)

    async def _handle_describe_screen(self, text: str) -> str | None:
        """
        处理"描述屏幕"请求。

        Args:
            text: 用户输入。

        Returns:
            AI回复（包含屏幕描述）。
        """
        if not self.vision.is_camera_available and True:
            # 摄像头不可用但屏幕总是可用的
            pass

        description = await self.vision.describe_screen()
        if not description:
            return "抱歉，屏幕捕获失败了"

        return await self.brain.generate_with_vision(text, description)

    async def _handle_describe_camera(self, text: str) -> str | None:
        """
        处理"描述摄像头"请求。

        Args:
            text: 用户输入。

        Returns:
            AI回复（包含摄像头画面描述）。
        """
        if not self.vision.is_camera_available:
            return "摄像头不可用，请检查摄像头权限设置"

        description = await self.vision.describe_camera()
        if not description:
            return "抱歉，摄像头捕获失败了"

        return await self.brain.generate_with_vision(text, description)

    async def _handle_system_command(self, text: str) -> str | None:
        """
        处理系统命令。

        Args:
            text: 用户输入。

        Returns:
            执行结果。
        """
        text_lower = text.lower()

        if any(kw in text_lower for kw in ["暂停", "stop", "停止"]):
            self.voice.pause()
            return "好的，语音交互已暂停"

        elif any(kw in text_lower for kw in ["继续", "resume"]):
            self.voice.resume()
            return "好的，语音交互已恢复"

        elif any(kw in text_lower for kw in ["清空历史", "clear"]):
            self.brain.clear_history()
            return "对话历史已清空"

        elif any(kw in text_lower for kw in ["退出", "关闭", "quit", "exit"]):
            self._running = False
            return "好的，我先走了"

        return "我不太明白这个命令，你可以试试：暂停、继续、清空历史、退出"

    def _on_ai_speaking(self) -> None:
        """AI开始说话时的回调。"""
        self._logger.debug("AI开始播报")

    def _on_ai_done_speaking(self) -> None:
        """AI结束说话时的回调。"""
        self._logger.debug("AI播报结束")

    # ========================================================================
    # 主运行循环
    # ========================================================================

    async def run(self) -> None:
        """主运行循环 — 启动后保持运行直到收到停止信号。"""
        await self.start()

        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()


# ============================================================================
# 命令行入口
# ============================================================================

async def main_async(config_path: str | None = None) -> None:
    """异步主入口。"""
    butler = AIButler(config_path)
    await butler.run()


def main() -> None:
    """命令行入口点。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="AI Butler — macOS本地AI管家",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                     # 使用默认配置启动
  python main.py -c /path/to/config  # 指定配置文件
  python main.py -v DEBUG            # 调试模式
        """,
    )
    parser.add_argument(
        "-c", "--config",
        help="配置文件路径 (默认: config.yaml)",
        default=None,
    )
    parser.add_argument(
        "-v", "--verbose",
        help="日志级别 (默认: INFO)",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--pid-file",
        help="PID文件路径",
        default=None,
    )
    parser.add_argument(
        "--log-file",
        help="日志文件路径",
        default=None,
    )

    args = parser.parse_args()

    # 先加载配置以获取日志设置
    try:
        config = Config(args.config)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 设置日志
    log_level = args.verbose or config.get("general.log_level", "INFO")
    log_file = args.log_file or config.get("daemon.log_file")
    setup_logging(log_level, log_file)

    logger = logging.getLogger("main")

    # PID文件检查
    pid_file = args.pid_file or config.get("daemon.pid_file", "/tmp/ai-butler.pid")
    if check_pid(pid_file):
        logger.error(f"AI Butler 已在运行 (PID文件: {pid_file})")
        sys.exit(1)

    # 写入PID
    write_pid(pid_file)

    # 信号处理
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("收到退出信号，正在关闭...")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    async def run_with_shutdown():
        butler = AIButler(args.config)
        butler_task = asyncio.create_task(butler.run())

        # 等待关闭信号
        await shutdown_event.wait()

        # 触发butler关闭
        butler._running = False
        await butler.stop()
        butler_task.cancel()
        try:
            await butler_task
        except asyncio.CancelledError:
            pass

    try:
        logger.info(f"PID: {os.getpid()}")
        loop.run_until_complete(run_with_shutdown())
    except KeyboardInterrupt:
        pass
    finally:
        remove_pid(pid_file)
        loop.close()
        logger.info("再见!")


if __name__ == "__main__":
    main()
