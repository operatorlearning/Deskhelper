# -*- coding: utf-8 -*-
"""
文件名称：core/agent.py
文件用途：项目后端逻辑的中枢。它是一个典型的“中控”类，负责将各功能模块（如视觉模型、语音识别、
          任务规划器、执行器、记忆系统）整合在一起，并向前端提供统一的对话和任务执行接口。
"""

import sys  # 导入系统模块，用于操作 Python 运行环境
from pathlib import Path  # 导入路径操作模块，提供跨平台的路径处理
from typing import Optional  # 导入类型提示，用于标记可选变量

from loguru import logger  # 导入日志记录库，用于输出调试和运行信息

# 确保项目根目录在 Python 搜索路径中，以便能够正确导入同级或上级模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config  # 导入全局配置对象
from models.vision import VisionModel  # 导入视觉大模型接口类
from models.speech import WhisperSTT, TTSEngine  # 导入语音识别(STT)与文字转语音(TTS)引擎类
from models.ocr import OCREngine  # 导入文字识别 OCR 引擎类
from tools.screen import ScreenCapture  # 导入屏幕截取工具类
from tools.mouse_keyboard import MouseKeyboardController  # 导入鼠标键盘模拟控制类
from tools.file_ops import FileOps  # 导入文件系统操作工具类
from tools.app_control import AppController  # 导入第三方应用(如微信、浏览器)控制类
from core.memory import MemorySystem  # 导入记忆管理系统类
from core.planner import TaskPlanner  # 导入任务规划引擎类
from core.executor import TaskExecutor, ToolRegistry  # 导入任务执行器与工具注册表类

class DesktopAgent:
    """
    桌面智能助手的主 Agent 类，通过“组合”模式管理所有核心能力模块。
    """

    def __init__(self):
        """
        构造函数：初始化 Agent 实例及其依赖的各功能子模块。
        """
        logger.info("初始化桌面智能助手核心模块...")  # 记录初始化开始的日志

        # 定义高开销模块的属性并初始化为 None，采用“懒加载”策略以加快首次启动感知速度
        self._vision: Optional[VisionModel] = None  # 视觉模型实例占位
        self._stt: Optional[WhisperSTT] = None  # 语音识别引擎占位
        self._tts: Optional[TTSEngine] = None  # 语音合成引擎占位
        self._ocr: Optional[OCREngine] = None  # OCR 引擎占位

        # 实例化轻量级的、初始化速度快的、且运行必需的基础能力模块
        self.screen = ScreenCapture(config.screen)  # 初始化屏幕捕获模块，传入屏幕配置
        self.mk = MouseKeyboardController(config.screen)  # 初始化鼠标键盘控制模块
        self.file_ops = FileOps()  # 初始化文件操作基础工具集
        self.app_ctrl = AppController(self.mk)  # 初始化应用控制模块，并注入鼠标键盘控制器
        self.memory = MemorySystem(config.memory)  # 初始化记忆系统，管理向量数据库和对话记录

        # 初始化工具注册表：这是 Agent 所有可用技能（API）的清单汇总处
        self.registry = ToolRegistry()  # 创建工具注册中心实例
        self._register_tools()  # 调用私有方法，将各种具体操作绑定到注册表中

        # 初始化 LLM（大语言模型）加载状态标记为 False
        self._llm_loaded = False  # 用于追踪大模型是否已初始化完毕

        # 初始化规划系统与执行引擎
        self.planner: Optional[TaskPlanner] = None  # 任务规划器占位
        self.executor = TaskExecutor(  # 创建任务执行器实例
            tool_registry=self.registry,  # 传入可用的工具清单
            screen_capture=self.screen,  # 传入屏幕捕获模块
            vision_model=None,  # 初始时不传入视觉模型引用，等待懒加载完成
            memory_system=self.memory,  # 传入记忆系统以便执行中检索参考
        )

        logger.success("桌面智能助手核心初始化完毕")  # 记录成功初始化的日志

    # ---------- 模块懒加载属性：仅在代码第一次调用该属性时，才从磁盘加载模型至内存/显存 ----------

    @property
    def vision(self) -> VisionModel:
        """获取视觉模型实例，如果尚未加载则执行加载。"""
        if self._vision is None:  # 如果模型还没被创建
            self._vision = VisionModel(config.vision)  # 创建视觉大模型实例并加载权重
            self.executor.vision = self._vision  # 将新加载的视觉模型引用同步给执行器模块
        return self._vision  # 返回视觉模型实例

    @property
    def stt(self) -> WhisperSTT:
        """获取语音转文字引擎实例。"""
        if self._stt is None:  # 如果 STT 引擎还没被创建
            self._stt = WhisperSTT(config.whisper)  # 实例化 Whisper 语音识别引擎
        return self._stt  # 返回 STT 实例

    @property
    def tts(self) -> TTSEngine:
        """获取文字转语音引擎实例。"""
        if self._tts is None:  # 如果 TTS 引擎还没被创建
            self._tts = TTSEngine(config.tts)  # 实例化语音合成引擎
        return self._tts  # 返回 TTS 实例

    @property
    def ocr(self) -> OCREngine:
        """获取轻量级 OCR 文字识别引擎实例。"""
        if self._ocr is None:  # 如果 OCR 引擎还没被创建
            self._ocr = OCREngine()  # 实例化 OCR 引擎
        return self._ocr  # 返回 OCR 实例

    # ---------- 工具注册：将复杂的底层方法映射为 Agent 可以直接调用的“简易技能” ----------

    def _register_tools(self):
        """将底层实现代码注册到统一的工具注册表（ToolRegistry）中。"""
        mk = self.mk  # 局部变量引用键盘鼠标控制器
        sc = self.screen  # 局部变量引用屏幕捕获器
        fo = self.file_ops  # 局部变量引用文件操作器
        ac = self.app_ctrl  # 局部变量引用应用控制器

        # 注册键盘与鼠标模拟控制类技能
        self.registry.register("click", lambda x, y, button="left": mk.click(x, y, button=button))  # 注册点击功能
        self.registry.register("double_click", lambda x, y: mk.double_click(x, y))  # 注册双击功能
        self.registry.register("right_click", lambda x, y: mk.right_click(x, y))  # 注册右键功能
        self.registry.register("type_text", lambda text, chinese=False: mk.type_text_chinese(text) if chinese else mk.type_text(text))  # 注册输入文本功能
        self.registry.register("hotkey", lambda keys: mk.hotkey(*keys.split("+")))  # 注册组合快捷键功能
        self.registry.register("press_key", lambda key: mk.press_key(key))  # 注册单键按下功能
        self.registry.register("scroll", lambda x, y, direction="down", amount=3: mk.scroll(x, y, direction, amount))  # 注册滚轮滑动功能
        self.registry.register("move_to", lambda x, y: mk.move_to(x, y))  # 注册移动光标功能
        
        # 注册屏幕快照类技能
        self.registry.register("take_screenshot", lambda: sc.capture_full(save=True))  # 注册全屏截图功能
        self.registry.register("capture_region", lambda x, y, width, height: sc.capture_region(x, y, width, height))  # 注册区域截图功能
        
        # 注册文件系统操作类技能
        self.registry.register("read_file", lambda path: fo.read_text(path))  # 注册读取文件功能
        self.registry.register("write_file", lambda path, content: fo.write_text(path, content))  # 注册写入文件功能
        self.registry.register("copy_file", lambda src, dst: fo.copy_file(src, dst))  # 注册复制文件功能
        self.registry.register("move_file", lambda src, dst: fo.move_file(src, dst))  # 注册移动文件功能
        self.registry.register("delete_file", lambda path: fo.delete_file(path))  # 注册删除文件功能
        self.registry.register("list_dir", lambda path, pattern="*": fo.list_dir(path, pattern))  # 注册查看目录功能
        self.registry.register("search_files", lambda directory, name_pattern, content_keyword=None: fo.search_files(directory, name_pattern, content_keyword))  # 注册文件搜索功能
        
        # 注册应用程序控制类技能
        self.registry.register("focus_window", lambda title: ac.focus_window(title))  # 注册窗口激活/聚焦功能
        self.registry.register("launch_app", lambda exe_path, args=None: ac.launch_app(exe_path, args))  # 注册启动外部应用功能
        self.registry.register("kill_app", lambda process_name: ac.kill_app(process_name))  # 注册关闭/强杀进程功能
        self.registry.register("open_url", lambda url: ac.open_url(url))  # 注册打开网址功能
        self.registry.register("send_wechat_message", lambda contact, message="", image_path=None: ac.send_wechat_message(contact, message, image_path))  # 注册发送微信消息功能
        self.registry.register("run_command", lambda command: ac.run_command(command))  # 注册执行 CMD 命令功能
        
        # 注册视觉辅助与搜索类技能
        self.registry.register("ocr_screen", self._ocr_screen)  # 注册全屏文字识别功能
        self.registry.register("find_text_on_screen", self._find_text_on_screen)  # 注册在屏幕查找特定文字并返回坐标的功能

        logger.debug(f"工具箱装载完毕，共计注册 {len(self.registry.list_tools())} 个核心工具")  # 记录已注册工具总数的调试日志

    def _ocr_screen(self) -> str:
        """私有辅助方法：获取当前屏幕实时截图并提取出所有可见的文字内容。"""
        img, _ = self.screen.capture_full(save=False)  # 截取全屏图片，暂不保存到硬盘
        return self.ocr.recognize_text_only(img)  # 使用 OCR 引擎识别并返回纯文本字符串

    def _find_text_on_screen(self, text: str):
        """私有辅助方法：在屏幕画面中定位指定的文字，并返回其精确的坐标信息。"""
        img, _ = self.screen.capture_full(save=False)  # 截取全屏图片
        positions = self.ocr.find_text_position(img, text)  # 在图中搜索目标文字的包围盒位置
        if positions:  # 如果找到了
            return f"找到 '{text}' 在坐标: {positions}"  # 返回格式化的坐标结果
        return f"未找到文字: '{text}'"  # 返回未找到的提示

    # ---------- LLM 交互逻辑与规划引擎控制 ----------

    def _load_llm(self):
        """初始化基于大型语言模型的规划引擎（Planner）。"""
        if self._llm_loaded:  # 如果已经加载过了，直接返回
            return
        logger.info("准备规划引擎，对接本地 LLM 推理接口...")  # 记录准备开始的日志
        _ = self.vision  # 通过访问 .vision 属性触发视觉模型的预加载
        self._llm_loaded = True  # 标记模型加载已完成
        self.planner = TaskPlanner(  # 实例化任务规划器
            llm_invoke_fn=self._llm_invoke,  # 传入负责调用推理底层的方法引用
            memory_system=self.memory,  # 注入记忆系统以便规划时参考知识库
            max_steps=config.agent.max_steps,  # 传入最大执行步数限制，防止死循环
        )
        logger.success("规划决策系统已激活")  # 记录成功的日志

    def _llm_invoke(self, prompt: str) -> str:
        """执行实际的本地大语言模型文本补全调用。"""
        return self.vision.invoke_text(prompt)  # 通过视觉模型对象的接口进行文本推理

    # ---------- 核心交互接口：前端 Web UI 与后端逻辑之间的通讯大门 ----------

    def chat(self, user_input: str, image=None) -> str:
        """
        处理用户的对话输入并返回回复文本。这是前端 Gradio 调用的主要接口。
        Args:
            user_input: 用户发送的文字指令。
            image: 用户手动上传的图片数据（可选）。
        Returns:
            AI 生成的文本回复。
        """
        self._load_llm()  # 确保在对话开始前，大模型推理环境已经加载
        self.memory.add_message("user", user_input)  # 将当前用户的输入添加到短期记忆和对话记录中
        
        # 执行知识检索：从向量库中寻找与当前用户输入相关联的历史背景或常识
        memory_ctx = self.memory.recall_as_context(user_input)  # 获取相关记忆上下文
        history = self.memory.get_conversation_history(n=8)  # 获取最近 8 轮的对话历史

        # 核心逻辑：意图路由选择，根据用户输入判断该走哪条处理路径
        if self._is_task_request(user_input):  # 如果输入包含动作关键词（如“打开”、“点击”）
            # 路径 A：自动化执行模式
            reply = self._execute_task(user_input)  # 调用规划与执行流处理任务
        elif image is not None:  # 如果用户没有发操作指令，但上传了一张图片
            # 路径 B：视觉分析模式
            reply = self.vision.analyze_image(image, user_input)  # 调用视觉模型分析这张图片
        else:  # 否则，视为普通的对话或知识问答
            # 路径 C：大语言模型闲聊/问答模式
            reply = self._pure_chat(user_input, history, memory_ctx)  # 结合历史和检索到的记忆进行回复

        self.memory.add_message("assistant", reply)  # 将 AI 生成的回复也存入记忆，完成上下文闭环
        return reply  # 将最终文本结果返回给前端显示

    def _is_task_request(self, text: str) -> bool:
        """
        利用预定义的动作关键词集合，快速判断用户是否请求执行某种实际操作。
        """
        task_keywords = [  # 定义识别任务请求的关键词库
            "帮我", "打开", "关闭", "发送", "复制", "移动", "删除",
            "截图", "搜索", "查找", "创建", "写入", "执行", "运行",
            "点击", "输入", "切换", "最大化", "最小化",
        ]
        return any(kw in text for kw in task_keywords)  # 检查文本中是否包含列表中的任意一个关键词

    def _execute_task(self, task: str) -> str:
        """
        执行多步自动化任务的闭环流程：规划 -> 调用工具执行 -> 总结结果。
        """
        try:  # 使用异常处理结构保证鲁棒性
            # 步骤 1：调用规划器，将复杂的模糊指令拆解为逻辑严密的具体步骤清单
            plan = self.planner.plan(task)  # 生成行动计划
            # 步骤 2：调用执行器，按照计划清单一步步调用系统工具与操作系统环境交互
            result = self.executor.execute_plan(plan)  # 执行并收集每一步的结果
            return result["summary"]  # 返回任务执行完毕后的最终结果汇总文本
        except Exception as e:  # 捕获执行过程中产生的任何错误
            logger.error(f"自动化任务流中断: {e}")  # 在后台终端打印详细错误日志
            return f"任务执行出错，已停止操作: {e}"  # 向用户返回友好的错误信息

    def _pure_chat(self, user_input: str, history: list, memory_ctx: str) -> str:
        """
        构建包含长短期记忆与系统提示词的完整 Prompt，并调用 LLM 生成纯文本对话回复。
        """
        # 构建记忆背景块：如果有相关的历史知识，则注入 Prompt 中
        memory_section = f"\n[历史相关记忆]:\n{memory_ctx}\n" if memory_ctx else ""  # 构建记忆引导文本
        history_text = ""  # 初始化对话历史文本字符串
        for msg in history[-6:]:  # 取最近的 6 条对话记录构建上下文
            role = "用户" if msg["role"] == "user" else "助手"  # 将内部角色名映射为中文说明
            history_text += f"{role}: {msg['content']}\n"  # 拼接对话历史行
        
        # 按照特定模板拼接 System Prompt（身份定义）、背景知识、对话历史和当前输入
        prompt = (
            f"{config.agent.system_prompt}\n"  # 注入全局系统角色定义
            f"{memory_section}"  # 注入 RAG 检索回来的长时记忆
            f"以下是我们的最近对话历史:\n{history_text}"  # 注入对话上下文
            f"用户当前请求: {user_input}\n"  # 注入用户当前正在问的问题
            f"助手请给出简洁友好的中文回答:"  # 给予 AI 最后的指令引导
        )
        return self._llm_invoke(prompt)  # 将拼好的长文本发给模型推理并返回结果

    def analyze_current_screen(self) -> str:
        """
        主动视觉观察接口：立即截取当前用户的物理桌面内容并进行视觉逻辑分析。
        """
        img, path = self.screen.capture_full(save=True)  # 截取全屏并强制保存一份到 data 目录，作为证据保留
        result = self.vision.analyze_screen(img)  # 调用视觉大模型进行全屏理解（描述当前开着什么应用等）
        # 将本次屏幕观察到的关键内容存入系统级别的系统消息记忆中，方便之后回答相关问题
        self.memory.add_message("system", f"我刚刚观察了你的屏幕，发现: {result[:200]}...")  # 仅记录摘要到记忆库
        return result  # 返回完整的分析结果给前端 UI 显示

    def transcribe_voice(self, audio_path: str = None) -> str:
        """
        语音转换接口：将录制的音频信号解析为可以处理的自然语言文字。
        """
        if audio_path:  # 如果传入了音频文件路径
            return self.stt.transcribe_file(audio_path)  # 调用 Whisper 转换现有的音频文件
        return self.stt.record_until_silence()  # 否则调用麦克风进入实时录音模式，直到检测到静默为止

    def speak(self, text: str):
        """
        语音播报接口：通过 TTS 引擎将文本异步转换为声音并播放给用户听。
        """
        self.tts.speak_async(text)  # 采用异步播放，防止语音播报阻塞主逻辑运行

    def get_status(self) -> dict:
        """
        健康检查与状态监控接口：实时汇报后端各个模型、工具及记忆系统的运行状态。
        """
        return {
            "name": config.agent.name,  # 返回 Agent 的名称
            "memory_count": self.memory.get_memory_count(),  # 返回向量库中的长期记忆条数
            "short_term_count": len(self.memory._short_term),  # 返回当前对话历史的短期记忆条数
            "tools_count": len(self.registry.list_tools()),  # 返回当前总共可用的工具数量
            "llm_loaded": self._llm_loaded,  # 返回大模型是否已加载完毕的状态
            "vision_loaded": self._vision is not None and self._vision._loaded,  # 视觉模型加载细节状态
            "whisper_loaded": self._stt is not None and self._stt._loaded,  # 语音识别模型加载细节状态
        }
