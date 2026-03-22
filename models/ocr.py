# -*- coding: utf-8 -*-
"""
OCR 模块 - 基于 PaddleOCR
支持中英文混合识别、表格识别、版面分析
"""

from pathlib import Path
from typing import Union, List, Dict, Tuple

from PIL import Image
from loguru import logger


class OCREngine:
    """PaddleOCR 封装"""

    def __init__(self):
        self.ocr = None
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        logger.info("正在加载 PaddleOCR 模型...")
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang="ch",           # 中英文混合
            use_gpu=True,
            show_log=False,
        )
        self._loaded = True
        logger.success("PaddleOCR 加载完成")

    def recognize(self, image: Union[str, Path, Image.Image]) -> List[Dict]:
        """
        识别图像中的文字
        Args:
            image: 图像路径或PIL Image
        Returns:
            [{"text": str, "confidence": float, "box": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]}]
        """
        self._load()

        if isinstance(image, Image.Image):
            import numpy as np
            image = np.array(image)
        else:
            image = str(image)

        result = self.ocr.ocr(image, cls=True)
        items = []
        if result and result[0]:
            for line in result[0]:
                box, (text, confidence) = line
                items.append({
                    "text": text,
                    "confidence": float(confidence),
                    "box": box,
                })
        logger.debug(f"OCR识别到 {len(items)} 个文本区域")
        return items

    def recognize_text_only(self, image: Union[str, Path, Image.Image]) -> str:
        """只返回识别到的纯文本（按行拼接）"""
        items = self.recognize(image)
        lines = [item["text"] for item in items]
        return "\n".join(lines)

    def find_text_position(
        self,
        image: Union[str, Path, Image.Image],
        target_text: str,
    ) -> List[Tuple[int, int]]:
        """
        查找特定文字的中心坐标
        Args:
            image: 图像
            target_text: 要查找的文字
        Returns:
            [(cx, cy), ...] 所有匹配位置的中心坐标列表
        """
        items = self.recognize(image)
        positions = []
        for item in items:
            if target_text in item["text"]:
                box = item["box"]
                cx = int(sum(p[0] for p in box) / 4)
                cy = int(sum(p[1] for p in box) / 4)
                positions.append((cx, cy))
                logger.debug(f"找到文字 '{target_text}' 在 ({cx}, {cy})")
        return positions

    def get_screen_text_map(
        self, image: Union[str, Path, Image.Image]
    ) -> str:
        """
        生成屏幕文字地图（用于给Agent理解界面）
        格式: 文字内容 @ (x, y)
        """
        items = self.recognize(image)
        lines = []
        for item in items:
            box = item["box"]
            cx = int(sum(p[0] for p in box) / 4)
            cy = int(sum(p[1] for p in box) / 4)
            lines.append(f"{item['text']} @ ({cx}, {cy})")
        return "\n".join(lines)

