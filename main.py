# -*- coding: utf-8 -*-
"""
文件名称：main.py
文件用途：项目的主启动入口文件。负责初始化日志系统、加载全局配置、实例化核心 Agent 模块，并最终启动基于 Gradio 的 Web 服务。
"""

import sys
import os
from pathlib import Path

# 确保项目根目录在 Python 搜索路径中，以便能够正确导入 core、ui 等自定义模块
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger  # 导入优秀的日志记录库 loguru
from config import config, LOG_DIR  # 导入项目配置及日志存储目录

def setup_logging():
    """
    配置日志系统的输出格式与存储策略。
    """
    # 移除 loguru 默认的控制台处理器
    logger.remove()
    
    # 添加新的控制台输出处理器，设置特定颜色和级别
    logger.add(
        sys.stderr,
        level=config.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan> - {message}",
        colorize=True,
    )
    
    # 添加文件日志记录器：按天滚动、保留7天、使用 UTF-8 编码，方便后续排查问题
    logger.add(
        str(LOG_DIR / "agent_{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        rotation="1 day",
        retention="7 days",
        encoding="utf-8",
    )

def print_banner():
    """
    在终端启动时打印项目的 ASCII 横幅装饰。
    """
    banner = r"""
 ╔══════════════════════════════════════════════════╗
 ║        桌面智能助手  Desktop AI Agent            ║
 ║  Qwen2.5-VL + Whisper + ChromaDB + LangChain    ║
 ║              本地运行 · 隐私安全                  ║
 ╚══════════════════════════════════════════════════╝
"""
    print(banner)

def main():
    """
    主程序逻辑执行流程。
    """
    # 1. 准备环境：配置日志和显示启动横幅
    setup_logging()
    print_banner()

    logger.info("正在初始化 Agent...")

    # 2. 延迟加载核心类：为了缩短启动感知时间，仅在需要时导入 DesktopAgent
    from core.agent import DesktopAgent
    agent = DesktopAgent()

    # 3. 输出初始化状态信息
    logger.info(f"Agent 初始化完成，工具数: {len(agent.registry.list_tools())}")
    logger.info(f"Web UI 地址: http://localhost:{config.ui_port}")
    logger.info("提示: 视觉模型和Whisper将在首次使用时加载（需要时间）")

    # 4. 初始化 UI 界面：调用 ui 模块创建 Gradio 块
    from ui.app import create_ui
    demo = create_ui(agent=agent)

    # 5. 启动 Gradio 服务器
    # inbrowser=False 确保不会自动在默认浏览器打开标签，配合 run_desktop.py 的 native 窗口使用
    demo.launch(
        server_name="127.0.0.1",
        server_port=config.ui_port,
        share=False,
        show_error=True,
        inbrowser=False,
    )

# 程序执行入口
if __name__ == "__main__":
    main()
