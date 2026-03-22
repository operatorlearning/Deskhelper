# -*- coding: utf-8 -*-
"""
屏幕捕获模块
支持：单屏截图、区域截图、连续截图、录屏
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image
from loguru import logger


class ScreenCapture:
    """屏幕捕获工具"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.screenshot_dir = Path(cfg.screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _gen_filename(self, prefix: str = "screenshot") -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return str(self.screenshot_dir / f"{prefix}_{ts}.png")

    def capture_full(self, save: bool = True) -> Tuple[Image.Image, Optional[str]]:
        """
        全屏截图
        Returns:
            (PIL.Image, 保存路径或None)
        """
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # 主显示器
            screenshot = sct.grab(monitor)
            img = Image.frombytes(
                "RGB",
                (screenshot.width, screenshot.height),
                screenshot.rgb,
            )
        path = None
        if save:
            path = self._gen_filename("full")
            img.save(path)
            logger.debug(f"全屏截图保存至: {path}")
        return img, path

    def capture_region(
        self,
        x: int, y: int, width: int, height: int,
        save: bool = True,
    ) -> Tuple[Image.Image, Optional[str]]:
        """
        区域截图
        Args:
            x, y: 左上角坐标
            width, height: 区域大小
        """
        import mss
        with mss.mss() as sct:
            monitor = {"top": y, "left": x, "width": width, "height": height}
            screenshot = sct.grab(monitor)
            img = Image.frombytes(
                "RGB",
                (screenshot.width, screenshot.height),
                screenshot.rgb,
            )
        path = None
        if save:
            path = self._gen_filename("region")
            img.save(path)
            logger.debug(f"区域截图保存至: {path}")
        return img, path

    def capture_window(self, window_title: str, save: bool = True) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        截取指定标题窗口
        Args:
            window_title: 窗口标题（支持部分匹配）
        """
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(window_title)
            if not windows:
                logger.warning(f"未找到窗口: {window_title}")
                return None, None
            win = windows[0]
            x, y, w, h = win.left, win.top, win.width, win.height
            return self.capture_region(x, y, w, h, save=save)
        except Exception as e:
            logger.error(f"截取窗口失败: {e}")
            return None, None

    def get_screen_size(self) -> Tuple[int, int]:
        """获取屏幕分辨率"""
        import mss
        with mss.mss() as sct:
            m = sct.monitors[1]
            return m["width"], m["height"]

    def start_recording(
        self,
        duration: float = 10.0,
        fps: int = 5,
        output_path: Optional[str] = None,
    ) -> str:
        """
        录制屏幕为视频
        Args:
            duration: 录制时长（秒）
            fps: 帧率
            output_path: 输出路径，默认自动生成
        Returns:
            视频文件路径
        """
        import cv2
        import mss
        import numpy as np

        if output_path is None:
            output_path = self._gen_filename("record").replace(".png", ".avi")

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            w, h = monitor["width"], monitor["height"]
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

            logger.info(f"开始录屏，时长 {duration}s，fps={fps}")
            start = time.time()
            while time.time() - start < duration:
                frame = np.array(sct.grab(monitor))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                out.write(frame)
                time.sleep(1.0 / fps)

            out.release()
            logger.info(f"录屏完成，保存至: {output_path}")

        return output_path

