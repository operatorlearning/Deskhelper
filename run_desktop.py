# -*- coding: utf-8 -*-
"""
浮窗模式启动器 — 以原生桌面窗口承载 Gradio UI
"""
import os
import sys
import subprocess
import time
import signal
from pathlib import Path

import urllib.request
import urllib.error

import webview

PROJECT_ROOT = Path(__file__).resolve().parent
PORT = int(os.getenv("UI_PORT", "7865"))
PYTHON = sys.executable


def wait_for_ui(url: str, timeout: float = 30.0, interval: float = 0.5):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except urllib.error.URLError:
            pass
        time.sleep(interval)
    raise TimeoutError(f"无法连接到 {url}，请确认后端是否启动成功。")


def start_backend() -> subprocess.Popen:
    env = os.environ.copy()
    env["UI_PORT"] = str(PORT)
    process = subprocess.Popen(
        [PYTHON, "main.py"],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return process


def stop_backend(process: subprocess.Popen):
    if process and process.poll() is None:
        # Windows 上 SIGINT 有兼容性问题，直接使用 terminate 或 CTRL_C_EVENT
        if sys.platform == "win32":
            process.terminate()
        else:
            process.send_signal(signal.SIGINT)
            
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    backend = None
    try:
        backend = start_backend()
        ui_url = f"http://127.0.0.1:{PORT}"
        print(f"正在启动桌面浮窗，接口地址：{ui_url}")
        wait_for_ui(ui_url)

        window = webview.create_window(
            title="AI 桌面助手",
            url=ui_url,
            width=460,
            height=720,
            resizable=True,
            confirm_close=True,
            on_top=True,
            background_color="#0a0c10",
        )
        webview.start(gui="edgechromium", debug=False)
    except Exception as exc:
        print(f"浮窗启动失败: {exc}")
        if backend:
            stop_backend(backend)
        sys.exit(1)
    finally:
        if backend:
            stop_backend(backend)
