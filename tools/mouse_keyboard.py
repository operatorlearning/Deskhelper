# -*- coding: utf-8 -*-
"""
鼠标键盘控制模块
基于 pyautogui 实现鼠标移动、点击、拖拽、键盘输入等操作
"""

import time
from typing import Optional, List, Tuple

import pyautogui
from loguru import logger

# 全局安全设置
pyautogui.FAILSAFE = True      # 鼠标移到左上角紧急停止
pyautogui.PAUSE = 0.1          # 每次操作后暂停0.1秒


class MouseKeyboardController:
    """鼠标键盘操作控制器"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.action_delay = cfg.action_delay
        self.mouse_duration = cfg.mouse_duration

    def _delay(self):
        time.sleep(self.action_delay)

    # ========== 鼠标操作 ==========

    def move_to(self, x: int, y: int):
        """移动鼠标到指定坐标"""
        logger.debug(f"鼠标移动到 ({x}, {y})")
        pyautogui.moveTo(x, y, duration=self.mouse_duration)
        self._delay()

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1):
        """
        点击指定位置
        Args:
            x, y: 坐标
            button: left/right/middle
            clicks: 点击次数（2为双击）
        """
        logger.info(f"{'双' if clicks == 2 else '单'}击 ({x}, {y}) [{button}]")
        pyautogui.click(x, y, button=button, clicks=clicks, duration=self.mouse_duration)
        self._delay()

    def double_click(self, x: int, y: int):
        """双击"""
        self.click(x, y, clicks=2)

    def right_click(self, x: int, y: int):
        """右键单击"""
        self.click(x, y, button="right")

    def drag(self, x1: int, y1: int, x2: int, y2: int):
        """从(x1,y1)拖拽到(x2,y2)"""
        logger.info(f"拖拽 ({x1},{y1}) -> ({x2},{y2})")
        pyautogui.drag(x2 - x1, y2 - y1, duration=self.mouse_duration * 2, button="left")
        self._delay()

    def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3):
        """
        滚动鼠标滚轮
        Args:
            direction: up/down
            amount: 滚动格数
        """
        pyautogui.moveTo(x, y)
        clicks = amount if direction == "up" else -amount
        pyautogui.scroll(clicks)
        logger.debug(f"滚轮 {direction} {amount} 格")
        self._delay()

    def get_position(self) -> Tuple[int, int]:
        """获取当前鼠标位置"""
        return pyautogui.position()

    # ========== 键盘操作 ==========

    def type_text(self, text: str, interval: float = 0.02):
        """
        输入文字
        Args:
            text: 要输入的文字
            interval: 每个字符间隔（秒）
        """
        logger.info(f"输入文字: {text[:30]}{'...' if len(text) > 30 else ''}")
        pyautogui.typewrite(text, interval=interval)
        self._delay()

    def type_text_chinese(self, text: str):
        """
        输入中文（通过剪贴板）
        Args:
            text: 中文文字
        """
        import pyperclip
        logger.info(f"输入中文: {text[:30]}{'...' if len(text) > 30 else ''}")
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        self._delay()

    def press_key(self, key: str):
        """
        按下并释放按键
        Args:
            key: 按键名称，如 'enter', 'tab', 'esc', 'f5' 等
        """
        logger.debug(f"按键: {key}")
        pyautogui.press(key)
        self._delay()

    def hotkey(self, *keys: str):
        """
        组合快捷键
        Args:
            keys: 按键序列，如 ('ctrl', 'c') 表示 Ctrl+C
        """
        logger.debug(f"快捷键: {'+'.join(keys)}")
        pyautogui.hotkey(*keys)
        self._delay()

    def key_down(self, key: str):
        """按住按键"""
        pyautogui.keyDown(key)

    def key_up(self, key: str):
        """释放按键"""
        pyautogui.keyUp(key)

    # ========== 组合操作 ==========

    def click_and_type(self, x: int, y: int, text: str, chinese: bool = False):
        """点击后输入文字"""
        self.click(x, y)
        time.sleep(0.2)
        if chinese:
            self.type_text_chinese(text)
        else:
            self.type_text(text)

    def select_all(self):
        """全选 (Ctrl+A)"""
        self.hotkey("ctrl", "a")

    def copy(self):
        """复制 (Ctrl+C)"""
        self.hotkey("ctrl", "c")

    def paste(self):
        """粘贴 (Ctrl+V)"""
        self.hotkey("ctrl", "v")

    def undo(self):
        """撤销 (Ctrl+Z)"""
        self.hotkey("ctrl", "z")

    def get_clipboard_text(self) -> str:
        """获取剪贴板文字"""
        import pyperclip
        return pyperclip.paste()

    def set_clipboard_text(self, text: str):
        """设置剪贴板文字"""
        import pyperclip
        pyperclip.copy(text)

    def screenshot_and_get_size(self):
        """获取屏幕尺寸"""
        return pyautogui.size()

