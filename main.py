# -*- coding: utf-8 -*-
"""
主入口文件
启动桌面AI助手
"""

import sys
import os
from pathlib import Path

# 确保项目根目录在Python路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from config import config, LOG_DIR


def setup_logging():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=config.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan> - {message}",
        colorize=True,
    )
    logger.add(
        str(LOG_DIR / "agent_{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        rotation="1 day",
        retention="7 days",
        encoding="utf-8",
    )


def print_banner():
    banner = r"""
 ╔══════════════════════════════════════════════════╗
 ║        桌面智能助手  Desktop AI Agent            ║
 ║  Qwen2.5-VL + Whisper + ChromaDB + LangChain    ║
 ║              本地运行 · 隐私安全                  ║
 ╚══════════════════════════════════════════════════╝
"""
    print(banner)


def main():
    setup_logging()
    print_banner()

    logger.info("正在初始化 Agent...")

    # 初始化主 Agent
    from core.agent import DesktopAgent
    agent = DesktopAgent()

    logger.info(f"Agent 初始化完成，工具数: {len(agent.registry.list_tools())}")
    logger.info(f"Web UI 地址: http://localhost:{config.ui_port}")
    logger.info("提示: 视觉模型和Whisper将在首次使用时加载（需要时间）")

    # 启动 Web UI
    from ui.app import create_ui
    demo = create_ui(agent=agent)

    demo.launch(
        server_name="127.0.0.1",
        server_port=config.ui_port,
        share=False,
        show_error=True,
        inbrowser=False,
    )


if __name__ == "__main__":
    main()

