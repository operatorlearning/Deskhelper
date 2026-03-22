# -*- coding: utf-8 -*-
"""
文件名称：run_desktop.py
文件用途：项目桌面端运行脚本。它通过 subprocess 启动 main.py 后端服务，并使用 pywebview 库创建一个原生的、
          始终置顶的桌面浮窗，将 Gradio 页面嵌入其中，从而实现“桌面小挂件”的使用体验。
"""
import os
import sys
import subprocess
import time
import signal
from pathlib import Path

import urllib.request
import urllib.error

import webview  # 用于创建原生桌面窗口的库

PROJECT_ROOT = Path(__file__).resolve().parent  # 项目根目录路径
PORT = int(os.getenv("UI_PORT", "7865"))         # 获取服务端口，默认为 7865
PYTHON = sys.executable                          # 当前 Python 解释器的路径

def wait_for_ui(url: str, timeout: float = 30.0, interval: float = 0.5):
    """
    循环检查后端服务是否已就绪。
    Args:
        url: 检查的地址
        timeout: 最大等待秒数
        interval: 每次检查的间隔秒数
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            # 尝试发送一个简单的 GET 请求，状态码为 200 则说明服务已启动
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except urllib.error.URLError:
            pass  # 服务尚未启动，继续等待
        time.sleep(interval)
    raise TimeoutError(f"无法连接到 {url}，请确认后端是否启动成功。")

def start_backend() -> subprocess.Popen:
    """
    在后台进程中启动 main.py 后端。
    """
    env = os.environ.copy()
    env["UI_PORT"] = str(PORT)
    # 使用 subprocess 启动进程，并将输出重定向到当前控制台
    process = subprocess.Popen(
        [PYTHON, "main.py"],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return process

def stop_backend(process: subprocess.Popen):
    """
    安全停止后端进程。
    """
    if process and process.poll() is None:
        # 跨平台信号处理：Windows 不支持 SIGINT 信号（会抛出 ValueError），改用 terminate
        if sys.platform == "win32":
            process.terminate()
        else:
            process.send_signal(signal.SIGINT)
            
        try:
            # 等待进程正常关闭，若超时则强行杀掉
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

if __name__ == "__main__":
    backend = None
    try:
        # 1. 启动后端进程
        backend = start_backend()
        ui_url = f"http://127.0.0.1:{PORT}"
        print(f"正在启动桌面浮窗，接口地址：{ui_url}")
        
        # 2. 等待后端 Gradio 就绪
        wait_for_ui(ui_url)

        # 3. 创建原生窗口并设置浮窗属性
        window = webview.create_window(
            title="AI 桌面助手",
            url=ui_url,
            width=460,        # 适合浮窗的窄宽度
            height=720,       # 适合移动端布局的高度
            resizable=True,   # 允许调整大小
            confirm_close=True,
            on_top=True,      # 核心功能：窗口始终保持在最前
            background_color="#0a0c10",
        )
        # 4. 启动 GUI（优先使用 Edge WebView2 引擎，关闭调试模式）
        webview.start(gui="edgechromium", debug=False)
    except Exception as exc:
        print(f"浮窗启动失败: {exc}")
        if backend:
            stop_backend(backend)
        sys.exit(1)
    finally:
        # 5. 窗口关闭后，同步关闭后端进程，防止端口占用
        if backend:
            stop_backend(backend)
