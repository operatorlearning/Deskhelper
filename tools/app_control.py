# -*- coding: utf-8 -*-
"""
跨应用操作模块
支持：启动/关闭应用、窗口管理、发送消息到微信/QQ等
基于 pywinauto + subprocess
"""

import os
import time
import subprocess
from typing import Optional, List, Tuple

from loguru import logger


class AppController:
    """跨应用控制器"""

    def __init__(self, mouse_kb_controller=None):
        """mouse_kb_controller: MouseKeyboardController 实例"""
        self.mk = mouse_kb_controller

    # ========== 进程管理 ==========

    def launch_app(self, exe_path: str, args: List[str] = None) -> subprocess.Popen:
        """启动应用程序"""
        cmd = [exe_path] + (args or [])
        logger.info(f"启动应用: {exe_path}")
        proc = subprocess.Popen(cmd)
        time.sleep(1.5)  # 等待应用启动
        return proc

    def kill_app(self, process_name: str) -> bool:
        """按进程名关闭应用"""
        import psutil
        killed = False
        for proc in psutil.process_iter(["pid", "name"]):
            if process_name.lower() in proc.info["name"].lower():
                proc.kill()
                logger.info(f"已关闭进程: {proc.info['name']} (PID {proc.info['pid']})")
                killed = True
        return killed

    def is_running(self, process_name: str) -> bool:
        """检查进程是否运行中"""
        import psutil
        for proc in psutil.process_iter(["name"]):
            if process_name.lower() in proc.info["name"].lower():
                return True
        return False

    def list_running_apps(self) -> List[dict]:
        """列出所有运行中的应用"""
        import psutil
        apps = []
        seen = set()
        for proc in psutil.process_iter(["pid", "name"]):
            name = proc.info["name"]
            if name not in seen:
                seen.add(name)
                apps.append({"pid": proc.info["pid"], "name": name})
        return apps

    # ========== 窗口管理 ==========

    def get_all_windows(self) -> List[str]:
        """获取所有可见窗口标题"""
        import pygetwindow as gw
        return gw.getAllTitles()

    def focus_window(self, title_keyword: str) -> bool:
        """激活/聚焦窗口"""
        try:
            import pygetwindow as gw
            windows = [w for w in gw.getAllWindows() if title_keyword in w.title]
            if not windows:
                logger.warning(f"未找到窗口: {title_keyword}")
                return False
            win = windows[0]
            win.activate()
            time.sleep(0.5)
            logger.info(f"已激活窗口: {win.title}")
            return True
        except Exception as e:
            logger.error(f"激活窗口失败: {e}")
            return False

    def maximize_window(self, title_keyword: str) -> bool:
        """最大化窗口"""
        try:
            import pygetwindow as gw
            windows = [w for w in gw.getAllWindows() if title_keyword in w.title]
            if windows:
                windows[0].maximize()
                return True
            return False
        except Exception as e:
            logger.error(f"最大化窗口失败: {e}")
            return False

    def minimize_window(self, title_keyword: str) -> bool:
        """最小化窗口"""
        try:
            import pygetwindow as gw
            windows = [w for w in gw.getAllWindows() if title_keyword in w.title]
            if windows:
                windows[0].minimize()
                return True
            return False
        except Exception as e:
            logger.error(f"最小化窗口失败: {e}")
            return False

    # ========== 浏览器操作 ==========

    def open_url(self, url: str, browser: str = "default"):
        """在浏览器中打开URL"""
        import webbrowser
        logger.info(f"打开URL: {url}")
        if browser == "default":
            webbrowser.open(url)
        elif browser == "chrome":
            webbrowser.get("chrome").open(url)
        time.sleep(1.5)

    # ========== 微信/QQ 操作（通过UI自动化）==========

    def send_wechat_message(
        self,
        contact: str,
        message: str,
        image_path: Optional[str] = None,
    ) -> bool:
        """
        通过微信桌面端发送消息/图片
        Args:
            contact: 联系人或群名
            message: 文字消息（可为空）
            image_path: 图片路径（可选）
        Returns:
            是否成功
        """
        if not self.mk:
            logger.error("需要 MouseKeyboardController 实例")
            return False

        logger.info(f"准备向 '{contact}' 发送微信消息")

        # 1. 激活微信窗口
        if not self.focus_window("微信"):
            logger.error("未找到微信窗口，请先打开微信")
            return False
        time.sleep(0.5)

        # 2. 搜索联系人
        self.mk.hotkey("ctrl", "f")  # 微信搜索快捷键
        time.sleep(0.5)
        self.mk.type_text_chinese(contact)
        time.sleep(1.0)
        self.mk.press_key("enter")
        time.sleep(0.8)

        # 3. 发送文字消息
        if message:
            self.mk.type_text_chinese(message)
            time.sleep(0.3)

        # 4. 发送图片
        if image_path:
            self.mk.hotkey("ctrl", "shift", "f")  # 发送文件
            time.sleep(1.0)
            # 在文件对话框中输入路径
            self.mk.type_text(image_path)
            time.sleep(0.3)
            self.mk.press_key("enter")
            time.sleep(0.5)

        # 5. 发送
        self.mk.press_key("enter")
        time.sleep(0.5)
        logger.success(f"已发送消息到 '{contact}'")
        return True

    def open_file_with_default_app(self, file_path: str):
        """用默认程序打开文件"""
        import os
        logger.info(f"打开文件: {file_path}")
        os.startfile(file_path)

    def run_command(self, command: str, shell: bool = True) -> Tuple[int, str, str]:
        """
        执行系统命令
        Returns:
            (returncode, stdout, stderr)
        """
        logger.info(f"执行命令: {command}")
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        return result.returncode, result.stdout, result.stderr

