# -*- coding: utf-8 -*-
"""
Ollama 视觉语言模型封装
通过 Ollama 本地 API 调用 qwen2.5vl / qwen3 等模型
无需手动下载权重，Ollama 自动管理
"""

import base64
import io
import httpx
from pathlib import Path
from typing import Union

from PIL import Image
from loguru import logger


OLLAMA_BASE_URL = "http://localhost:11434"


class VisionModel:
    """
    基于 Ollama 的视觉语言模型
    默认使用 qwen2.5vl:8b，也支持其他多模态模型
    """

    def __init__(self, cfg):
        self.cfg = cfg
        # Ollama 模型名称（优先用配置，否则默认）
        self.model_name = getattr(cfg, "ollama_model", "qwen2.5vl:8b")
        self.base_url = getattr(cfg, "ollama_url", OLLAMA_BASE_URL)
        self._loaded = False
        self.model = None      # 兼容旧代码引用
        self.processor = None  # 兼容旧代码引用

    def _load_model(self):
        """检查 Ollama 服务是否可用"""
        if self._loaded:
            return
        logger.info(f"连接 Ollama 服务: {self.base_url}")
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            models = [m["name"] for m in resp.json().get("models", [])]
            logger.info(f"Ollama 已有模型: {models}")
            # 检查目标模型是否存在
            matched = [m for m in models if self.model_name.split(":")[0] in m]
            if matched:
                self.model_name = matched[0]
                logger.success(f"使用模型: {self.model_name}")
            else:
                logger.warning(
                    f"未找到 {self.model_name}，将在首次调用时自动拉取。"
                    f"也可手动运行: ollama pull {self.model_name}"
                )
            self._loaded = True
        except Exception as e:
            logger.error(f"无法连接 Ollama: {e}")
            logger.error("请确认 Ollama 已启动: ollama serve")
            raise

    def _image_to_base64(self, image: Union[str, Path, Image.Image]) -> str:
        """图像转 base64"""
        if isinstance(image, (str, Path)):
            with open(image, "rb") as f:
                return base64.b64encode(f.read()).decode()
        elif isinstance(image, Image.Image):
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        raise ValueError(f"不支持的图像类型: {type(image)}")

    def _chat(self, prompt: str, image: Union[str, Path, Image.Image, None] = None) -> str:
        """调用 Ollama chat API"""
        self._load_model()

        # /no_think 指令让 qwen3 系列跳过思考过程，直接输出回答
        msg = {"role": "user", "content": f"/no_think\n{prompt}"}
        if image is not None:
            msg["images"] = [self._image_to_base64(image)]

        payload = {
            "model": self.model_name,
            "messages": [msg],
            "stream": False,
            "options": {
                "num_predict": 2048,
                "temperature": 0.1,
                "num_ctx": 8192,
            },
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                logger.error(f"Ollama API 错误: {data['error']}")
                return f"❌ Ollama API 错误: {data['error']}"
            if "message" in data and "content" in data["message"]:
                return data["message"]["content"]
            logger.error(f"Ollama 返回异常: {data}")
            return f"❌ Ollama 返回异常: {data}"
        except httpx.TimeoutException:
            logger.error("Ollama 响应超时，模型可能正在加载，请稍后重试")
            return "❌ Ollama 响应超时，模型可能正在加载，请稍后重试"
        except Exception as e:
            logger.error(f"Ollama 调用失败: {e}")
            return f"❌ Ollama 调用失败: {e}"

    def analyze_image(
        self,
        image: Union[str, Path, Image.Image],
        question: str = "请详细描述这张图片的内容，包括所有可见的文字、界面元素和操作建议。",
    ) -> str:
        """分析图像内容"""
        logger.debug(f"分析图像，问题: {question[:50]}")
        result = self._chat(question, image)
        logger.debug(f"视觉分析结果: {result[:100]}")
        return result

    def analyze_screen(self, screenshot: Union[str, Path, Image.Image]) -> str:
        """分析屏幕截图"""
        question = (
            "请详细分析这张屏幕截图：\n"
            "1. 当前打开的应用程序和窗口\n"
            "2. 屏幕上的所有可见文字内容\n"
            "3. 可交互的UI元素（按钮、输入框、菜单等）\n"
            "4. 当前界面的功能和状态\n"
            "5. 建议的下一步操作"
        )
        return self.analyze_image(screenshot, question)

    def find_element(
        self,
        screenshot: Union[str, Path, Image.Image],
        element_description: str,
    ) -> str:
        """在截图中定位UI元素"""
        question = (
            f"请在这张截图中找到「{element_description}」。\n"
            "1. 该元素是否存在？\n"
            "2. 元素的大概位置（左上/中间/右下等）\n"
            "3. 元素的精确像素坐标（x, y）估计\n"
            "4. 元素的外观特征"
        )
        return self.analyze_image(screenshot, question)

    def ocr_image(self, image: Union[str, Path, Image.Image]) -> str:
        """OCR文字识别"""
        return self.analyze_image(
            image,
            "请识别并提取这张图片中的所有文字内容，按从上到下、从左到右的顺序输出。"
        )

    def understand_task_context(
        self,
        screenshot: Union[str, Path, Image.Image],
        task: str,
    ) -> str:
        """结合任务理解当前屏幕状态"""
        question = (
            f"用户的任务是：{task}\n\n"
            "请分析当前屏幕状态，给出：\n"
            "1. 当前界面是否与任务相关\n"
            "2. 为完成任务，下一步应该执行什么操作\n"
            "3. 需要点击/输入的具体位置和内容\n"
            "4. 潜在的风险或注意事项"
        )
        return self.analyze_image(screenshot, question)

    def invoke_text(self, prompt: str) -> str:
        """纯文本推理（无图像），用于规划和对话"""
        return self._chat(prompt)
