# -*- coding: utf-8 -*-
"""
主 Agent 核心
集成 LangChain + Qwen2.5-VL + 工具链 + 记忆系统
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# 确保项目根目录在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from models.vision import VisionModel
from models.speech import WhisperSTT, TTSEngine
from models.ocr import OCREngine
from tools.screen import ScreenCapture
from tools.mouse_keyboard import MouseKeyboardController
from tools.file_ops import FileOps
from tools.app_control import AppController
from core.memory import MemorySystem
from core.planner import TaskPlanner
from core.executor import TaskExecutor, ToolRegistry


class DesktopAgent:
    """
    桌面智能助手主 Agent
    """

    def __init__(self):
        logger.info("初始化桌面智能助手...")

        # 各模块（懒加载）
        self._vision: Optional[VisionModel] = None
        self._stt: Optional[WhisperSTT] = None
        self._tts: Optional[TTSEngine] = None
        self._ocr: Optional[OCREngine] = None

        # 立即初始化的轻量模块
        self.screen = ScreenCapture(config.screen)
        self.mk = MouseKeyboardController(config.screen)
        self.file_ops = FileOps()
        self.app_ctrl = AppController(self.mk)
        self.memory = MemorySystem(config.memory)

        # 工具注册表
        self.registry = ToolRegistry()
        self._register_tools()

        # LLM状态
        self._llm_loaded = False

        # 规划器 & 执行器
        self.planner: Optional[TaskPlanner] = None
        self.executor = TaskExecutor(
            tool_registry=self.registry,
            screen_capture=self.screen,
            vision_model=None,
            memory_system=self.memory,
        )

        logger.success("桌面智能助手初始化完成")

    # ---------- 模块懒加载属性 ----------

    @property
    def vision(self) -> VisionModel:
        if self._vision is None:
            self._vision = VisionModel(config.vision)
            self.executor.vision = self._vision
        return self._vision

    @property
    def stt(self) -> WhisperSTT:
        if self._stt is None:
            self._stt = WhisperSTT(config.whisper)
        return self._stt

    @property
    def tts(self) -> TTSEngine:
        if self._tts is None:
            self._tts = TTSEngine(config.tts)
        return self._tts

    @property
    def ocr(self) -> OCREngine:
        if self._ocr is None:
            self._ocr = OCREngine()
        return self._ocr

    # ---------- 工具注册 ----------

    def _register_tools(self):
        """注册所有工具到 ToolRegistry"""
        mk = self.mk
        sc = self.screen
        fo = self.file_ops
        ac = self.app_ctrl

        self.registry.register("click", lambda x, y, button="left": mk.click(x, y, button=button))
        self.registry.register("double_click", lambda x, y: mk.double_click(x, y))
        self.registry.register("right_click", lambda x, y: mk.right_click(x, y))
        self.registry.register("type_text", lambda text, chinese=False: mk.type_text_chinese(text) if chinese else mk.type_text(text))
        self.registry.register("hotkey", lambda keys: mk.hotkey(*keys.split("+")))
        self.registry.register("press_key", lambda key: mk.press_key(key))
        self.registry.register("scroll", lambda x, y, direction="down", amount=3: mk.scroll(x, y, direction, amount))
        self.registry.register("move_to", lambda x, y: mk.move_to(x, y))
        self.registry.register("take_screenshot", lambda: sc.capture_full(save=True))
        self.registry.register("capture_region", lambda x, y, width, height: sc.capture_region(x, y, width, height))
        self.registry.register("read_file", lambda path: fo.read_text(path))
        self.registry.register("write_file", lambda path, content: fo.write_text(path, content))
        self.registry.register("copy_file", lambda src, dst: fo.copy_file(src, dst))
        self.registry.register("move_file", lambda src, dst: fo.move_file(src, dst))
        self.registry.register("delete_file", lambda path: fo.delete_file(path))
        self.registry.register("list_dir", lambda path, pattern="*": fo.list_dir(path, pattern))
        self.registry.register("search_files", lambda directory, name_pattern, content_keyword=None: fo.search_files(directory, name_pattern, content_keyword))
        self.registry.register("focus_window", lambda title: ac.focus_window(title))
        self.registry.register("launch_app", lambda exe_path, args=None: ac.launch_app(exe_path, args))
        self.registry.register("kill_app", lambda process_name: ac.kill_app(process_name))
        self.registry.register("open_url", lambda url: ac.open_url(url))
        self.registry.register("send_wechat_message", lambda contact, message="", image_path=None: ac.send_wechat_message(contact, message, image_path))
        self.registry.register("run_command", lambda command: ac.run_command(command))
        self.registry.register("ocr_screen", self._ocr_screen)
        self.registry.register("find_text_on_screen", self._find_text_on_screen)

        logger.debug(f"已注册 {len(self.registry.list_tools())} 个工具")

    def _ocr_screen(self) -> str:
        img, _ = self.screen.capture_full(save=False)
        return self.ocr.recognize_text_only(img)

    def _find_text_on_screen(self, text: str):
        img, _ = self.screen.capture_full(save=False)
        positions = self.ocr.find_text_position(img, text)
        if positions:
            return f"找到 '{text}' 在坐标: {positions}"
        return f"未找到文字: '{text}'"

    # ---------- LLM 加载 ----------

    def _load_llm(self):
        """初始化规划器（Ollama 无需预加载，按需调用）"""
        if self._llm_loaded:
            return
        logger.info("初始化规划器，使用 Ollama 模型...")
        # 预检 Ollama 连接
        _ = self.vision
        self._llm_loaded = True
        self.planner = TaskPlanner(
            llm_invoke_fn=self._llm_invoke,
            memory_system=self.memory,
            max_steps=config.agent.max_steps,
        )
        logger.success("规划器初始化完成")

    def _llm_invoke(self, prompt: str) -> str:
        """调用 Ollama 模型进行纯文本推理"""
        return self.vision.invoke_text(prompt)

    # ---------- 对话接口 ----------

    def chat(self, user_input: str, image=None) -> str:
        """
        主对话接口
        Args:
            user_input: 用户文字输入
            image: 可选图像（PIL Image 或路径）
        """
        self._load_llm()
        self.memory.add_message("user", user_input)
        memory_ctx = self.memory.recall_as_context(user_input)
        history = self.memory.get_conversation_history(n=8)

        if self._is_task_request(user_input):
            reply = self._execute_task(user_input)
        elif image is not None:
            reply = self.vision.analyze_image(image, user_input)
        else:
            reply = self._pure_chat(user_input, history, memory_ctx)

        self.memory.add_message("assistant", reply)
        return reply

    def _is_task_request(self, text: str) -> bool:
        """判断是否为需要执行操作的任务请求"""
        task_keywords = [
            "帮我", "打开", "关闭", "发送", "复制", "移动", "删除",
            "截图", "搜索", "查找", "创建", "写入", "执行", "运行",
            "点击", "输入", "切换", "最大化", "最小化",
        ]
        return any(kw in text for kw in task_keywords)

    def _execute_task(self, task: str) -> str:
        """规划并执行任务"""
        try:
            plan = self.planner.plan(task)
            result = self.executor.execute_plan(plan)
            return result["summary"]
        except Exception as e:
            logger.error(f"任务执行异常: {e}")
            return f"任务执行出错: {e}"

    def _pure_chat(self, user_input: str, history: list, memory_ctx: str) -> str:
        """纯对话（不执行操作）"""
        memory_section = f"\n{memory_ctx}\n" if memory_ctx else ""
        history_text = ""
        for msg in history[-6:]:
            role = "用户" if msg["role"] == "user" else "助手"
            history_text += f"{role}: {msg['content']}\n"
        prompt = (
            f"{config.agent.system_prompt}\n"
            f"{memory_section}"
            f"对话历史:\n{history_text}"
            f"用户: {user_input}\n"
            f"助手:"
        )
        return self._llm_invoke(prompt)

    def analyze_current_screen(self) -> str:
        """分析当前屏幕"""
        img, path = self.screen.capture_full(save=True)
        result = self.vision.analyze_screen(img)
        self.memory.add_message("system", f"屏幕分析: {result[:200]}")
        return result

    def transcribe_voice(self, audio_path: str = None) -> str:
        """语音转文字"""
        if audio_path:
            return self.stt.transcribe_file(audio_path)
        return self.stt.record_until_silence()

    def speak(self, text: str):
        """语音播报"""
        self.tts.speak_async(text)

    def get_status(self) -> dict:
        """获取Agent状态"""
        return {
            "name": config.agent.name,
            "memory_count": self.memory.get_memory_count(),
            "short_term_count": len(self.memory._short_term),
            "tools_count": len(self.registry.list_tools()),
            "llm_loaded": self._llm_loaded,
            "vision_loaded": self._vision is not None and self._vision._loaded,
            "whisper_loaded": self._stt is not None and self._stt._loaded,
        }
