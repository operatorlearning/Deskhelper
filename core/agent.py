# -*- coding: utf-8 -*-
"""
文件名称：core/agent.py
文件用途：项目后端逻辑的中枢。它是一个典型的“中控”类，负责将各功能模块（如视觉模型、语音识别、
          任务规划器、执行器、记忆系统）整合在一起，并向前端提供统一的对话和任务执行接口。
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# 确保项目根目录在 Python 搜索路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config  # 全局配置对象
from models.vision import VisionModel  # 视觉大模型接口
from models.speech import WhisperSTT, TTSEngine  # 语音识别(STT)与播报(TTS)引擎
from models.ocr import OCREngine  # 文字识别 OCR 引擎
from tools.screen import ScreenCapture  # 截图工具类
from tools.mouse_keyboard import MouseKeyboardController  # 鼠标键盘模拟器
from tools.file_ops import FileOps  # 文件操作工具类
from tools.app_control import AppController  # 微信/浏览器等应用控制
from core.memory import MemorySystem  # 向量数据库+长短时记忆管理
from core.planner import TaskPlanner  # 负责将自然语言拆解为执行步骤
from core.executor import TaskExecutor, ToolRegistry  # 负责逐步调用工具执行任务

class DesktopAgent:
    """
    桌面智能助手的主类，通过“组合”模式管理所有核心能力。
    """

    def __init__(self):
        logger.info("初始化桌面智能助手核心模块...")

        # 各高开销模块初始化为 None，采用“懒加载”策略以加快启动速度
        self._vision: Optional[VisionModel] = None
        self._stt: Optional[WhisperSTT] = None
        self._tts: Optional[TTSEngine] = None
        self._ocr: Optional[OCREngine] = None

        # 实例化轻量级的、必需的基础能力模块
        self.screen = ScreenCapture(config.screen)              # 屏幕抓取
        self.mk = MouseKeyboardController(config.screen)        # 输入模拟
        self.file_ops = FileOps()                               # 文件处理
        self.app_ctrl = AppController(self.mk)                  # 应用操控
        self.memory = MemorySystem(config.memory)               # 记忆检索

        # 初始化工具注册中心：这是 Agent “手臂”的汇总处
        self.registry = ToolRegistry()
        self._register_tools()

        # 追踪 LLM（大语言模型）的加载状态
        self._llm_loaded = False

        # 初始化执行器（负责拿着“工具”干活的模块）
        self.planner: Optional[TaskPlanner] = None
        self.executor = TaskExecutor(
            tool_registry=self.registry,
            screen_capture=self.screen,
            vision_model=None, # 初始时不传递视觉模型，等待懒加载完成
            memory_system=self.memory,
        )

        logger.success("桌面智能助手核心初始化完毕")

    # ---------- 模块懒加载属性：仅在第一次访问时加载大型模型，减少显存消耗 ----------

    @property
    def vision(self) -> VisionModel:
        """获取视觉模型实例，如果未加载则从磁盘载入。"""
        if self._vision is None:
            self._vision = VisionModel(config.vision)
            self.executor.vision = self._vision # 同步更新执行器的模型引用
        return self._vision

    @property
    def stt(self) -> WhisperSTT:
        """获取语音转文字引擎。"""
        if self._stt is None:
            self._stt = WhisperSTT(config.whisper)
        return self._stt

    @property
    def tts(self) -> TTSEngine:
        """获取文字转语音引擎。"""
        if self._tts is None:
            self._tts = TTSEngine(config.tts)
        return self._tts

    @property
    def ocr(self) -> OCREngine:
        """获取轻量级文字识别引擎。"""
        if self._ocr is None:
            self._ocr = OCREngine()
        return self._ocr

    # ---------- 工具注册：将具体的底层方法映射为 Agent 可识别的“能力” ----------

    def _register_tools(self):
        """将底层实现代码注册到统一的工具注册表。"""
        mk = self.mk
        sc = self.screen
        fo = self.file_ops
        ac = self.app_ctrl

        # 键盘与鼠标模拟操作
        self.registry.register("click", lambda x, y, button="left": mk.click(x, y, button=button))
        self.registry.register("double_click", lambda x, y: mk.double_click(x, y))
        self.registry.register("right_click", lambda x, y: mk.right_click(x, y))
        self.registry.register("type_text", lambda text, chinese=False: mk.type_text_chinese(text) if chinese else mk.type_text(text))
        self.registry.register("hotkey", lambda keys: mk.hotkey(*keys.split("+")))
        self.registry.register("press_key", lambda key: mk.press_key(key))
        self.registry.register("scroll", lambda x, y, direction="down", amount=3: mk.scroll(x, y, direction, amount))
        self.registry.register("move_to", lambda x, y: mk.move_to(x, y))
        
        # 屏幕图像获取
        self.registry.register("take_screenshot", lambda: sc.capture_full(save=True))
        self.registry.register("capture_region", lambda x, y, width, height: sc.capture_region(x, y, width, height))
        
        # 文件系统底层操作
        self.registry.register("read_file", lambda path: fo.read_text(path))
        self.registry.register("write_file", lambda path, content: fo.write_text(path, content))
        self.registry.register("copy_file", lambda src, dst: fo.copy_file(src, dst))
        self.registry.register("move_file", lambda src, dst: fo.move_file(src, dst))
        self.registry.register("delete_file", lambda path: fo.delete_file(path))
        self.registry.register("list_dir", lambda path, pattern="*": fo.list_dir(path, pattern))
        self.registry.register("search_files", lambda directory, name_pattern, content_keyword=None: fo.search_files(directory, name_pattern, content_keyword))
        
        # 应用程序高层控制
        self.registry.register("focus_window", lambda title: ac.focus_window(title))
        self.registry.register("launch_app", lambda exe_path, args=None: ac.launch_app(exe_path, args))
        self.registry.register("kill_app", lambda process_name: ac.kill_app(process_name))
        self.registry.register("open_url", lambda url: ac.open_url(url))
        self.registry.register("send_wechat_message", lambda contact, message="", image_path=None: ac.send_wechat_message(contact, message, image_path))
        self.registry.register("run_command", lambda command: ac.run_command(command))
        
        # 屏幕文字搜索能力
        self.registry.register("ocr_screen", self._ocr_screen)
        self.registry.register("find_text_on_screen", self._find_text_on_screen)

        logger.debug(f"工具箱装载完毕，共计注册 {len(self.registry.list_tools())} 个核心工具")

    def _ocr_screen(self) -> str:
        """获取当前屏幕快照并解析出所有可见文本。"""
        img, _ = self.screen.capture_full(save=False)
        return self.ocr.recognize_text_only(img)

    def _find_text_on_screen(self, text: str):
        """在屏幕上通过文字寻找对应的视觉坐标，方便后续点击。"""
        img, _ = self.screen.capture_full(save=False)
        positions = self.ocr.find_text_position(img, text)
        if positions:
            return f"找到 '{text}' 在坐标: {positions}"
        return f"未找到文字: '{text}'"

    # ---------- LLM 交互与规划引擎 ----------

    def _load_llm(self):
        """初始化基于 LLM 的规划器模块。"""
        if self._llm_loaded:
            return
        logger.info("准备规划引擎，对接本地 LLM 推理接口...")
        _ = self.vision # 确保推理模型已就绪
        self._llm_loaded = True
        self.planner = TaskPlanner(
            llm_invoke_fn=self._llm_invoke,
            memory_system=self.memory,
            max_steps=config.agent.max_steps,
        )
        logger.success("规划决策系统已激活")

    def _llm_invoke(self, prompt: str) -> str:
        """调用底层的文本补全方法，提供自然语言逻辑。"""
        return self.vision.invoke_text(prompt)

    # ---------- 对话式用户接口：前端 UI 调用的核心方法 ----------

    def chat(self, user_input: str, image=None) -> str:
        """
        处理用户输入的对话流。
        Args:
            user_input: 用户的自然语言指令。
            image: 用户手动上传的图片（可选）。
        Returns:
            回复文本。
        """
        self._load_llm() # 确保后端逻辑已加载
        self.memory.add_message("user", user_input) # 将用户输入记入短期记忆
        
        # 检索相关知识：通过向量库找回与当前问题相关的历史
        memory_ctx = self.memory.recall_as_context(user_input)
        history = self.memory.get_conversation_history(n=8) # 获取多轮对话上下文

        # 根据用户输入的意图选择处理路径：
        if self._is_task_request(user_input):
            # 路径 A：如果用户有操作意图（如“打开网页”），进入规划执行流
            reply = self._execute_task(user_input)
        elif image is not None:
            # 路径 B：如果用户上传了图片且没有操作意图，执行视觉理解
            reply = self.vision.analyze_image(image, user_input)
        else:
            # 路径 C：普通闲聊或知识问答，结合记忆和上下文进行对话生成
            reply = self._pure_chat(user_input, history, memory_ctx)

        self.memory.add_message("assistant", reply) # 将 AI 的回答也记入记忆
        return reply

    def _is_task_request(self, text: str) -> bool:
        """使用关键词快速预判用户是否需要系统执行某种操作（Task-oriented）。"""
        task_keywords = [
            "帮我", "打开", "关闭", "发送", "复制", "移动", "删除",
            "截图", "搜索", "查找", "创建", "写入", "执行", "运行",
            "点击", "输入", "切换", "最大化", "最小化",
        ]
        return any(kw in text for kw in task_keywords)

    def _execute_task(self, task: str) -> str:
        """多步任务执行核心逻辑：规划 -> 循环执行 -> 汇总结果。"""
        try:
            # 1. 拆解任务为具体的动作序列
            plan = self.planner.plan(task)
            # 2. 调用执行器按照规划，通过一系列工具调用与环境交互
            result = self.executor.execute_plan(plan)
            return result["summary"] # 返回最终任务结果的总结
        except Exception as e:
            logger.error(f"自动化任务流中断: {e}")
            return f"任务执行出错，已停止操作: {e}"

    def _pure_chat(self, user_input: str, history: list, memory_ctx: str) -> str:
        """构建完整的 Prompt 进行高质量的对话生成。"""
        memory_section = f"\n[历史相关记忆]:\n{memory_ctx}\n" if memory_ctx else ""
        history_text = ""
        for msg in history[-6:]:
            role = "用户" if msg["role"] == "user" else "助手"
            history_text += f"{role}: {msg['content']}\n"
        
        # 拼接系统预置提示词、相关记忆背景、对话历史以及当前问题
        prompt = (
            f"{config.agent.system_prompt}\n"
            f"{memory_section}"
            f"以下是我们的最近对话历史:\n{history_text}"
            f"用户当前请求: {user_input}\n"
            f"助手请给出简洁友好的中文回答:"
        )
        return self._llm_invoke(prompt)

    def analyze_current_screen(self) -> str:
        """直接触发当前屏幕内容的视觉理解服务。"""
        img, path = self.screen.capture_full(save=True)
        result = self.vision.analyze_screen(img)
        # 将分析结果记入系统日志/记忆，方便后续问答引用
        self.memory.add_message("system", f"我刚刚观察了你的屏幕，发现: {result[:200]}...")
        return result

    def transcribe_voice(self, audio_path: str = None) -> str:
        """将语音信号转换为文字内容。"""
        if audio_path:
            return self.stt.transcribe_file(audio_path) # 处理文件
        return self.stt.record_until_silence() # 实时录音识别

    def speak(self, text: str):
        """通过语音引擎将文本念给用户听。"""
        self.tts.speak_async(text)

    def get_status(self) -> dict:
        """健康检查接口：实时查看后端各模块（视觉、语音、内存）的就绪状态。"""
        return {
            "name": config.agent.name,
            "memory_count": self.memory.get_memory_count(),
            "short_term_count": len(self.memory._short_term),
            "tools_count": len(self.registry.list_tools()),
            "llm_loaded": self._llm_loaded,
            "vision_loaded": self._vision is not None and self._vision._loaded,
            "whisper_loaded": self._stt is not None and self._stt._loaded,
        }
