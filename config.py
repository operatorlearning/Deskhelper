# -*- coding: utf-8 -*-
"""
配置中心 - 所有模型路径、参数、系统配置统一管理
"""

import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = DATA_DIR / "memory"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
AUDIO_DIR = DATA_DIR / "audio"
LOG_DIR = BASE_DIR / "logs"

# 确保目录存在
for d in [DATA_DIR, MEMORY_DIR, SCREENSHOT_DIR, AUDIO_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class VisionConfig(BaseModel):
    """Ollama 视觉模型配置"""
    # Ollama 中的模型名称
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3-vl:8b")
    # Ollama 服务地址
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    # 最大生成token数
    max_new_tokens: int = 512
    # 以下保留兼容字段（不再使用）
    model_name: str = "qwen2.5vl:8b"
    local_model_path: str = ""
    torch_dtype: str = "float16"
    use_4bit: bool = False
    device: str = "cuda"
    min_pixels: int = 256 * 28 * 28
    max_pixels: int = 1280 * 28 * 28


class WhisperConfig(BaseModel):
    """Whisper 语音识别配置"""
    # 模型规格: tiny/base/small/medium/large
    model_size: str = os.getenv("WHISPER_MODEL", "medium")
    # 识别语言
    language: str = "zh"
    # 采样率
    sample_rate: int = 16000
    # 录音时长（秒）
    record_duration: int = 10
    # 设备
    device: str = os.getenv("WHISPER_DEVICE", "cuda")


class TTSConfig(BaseModel):
    """TTS 语音合成配置"""
    # 引擎: pyttsx3 (离线) | edge-tts (微软在线)
    engine: str = os.getenv("TTS_ENGINE", "pyttsx3")
    # edge-tts 中文声音
    edge_voice: str = "zh-CN-XiaoxiaoNeural"
    # pyttsx3 语速
    rate: int = 180
    # 音量 0.0-1.0
    volume: float = 0.9
    # 音频输出目录
    output_dir: str = str(AUDIO_DIR)


class MemoryConfig(BaseModel):
    """记忆系统配置（ChromaDB + RAG）"""
    # ChromaDB持久化目录
    persist_dir: str = str(MEMORY_DIR)
    # 嵌入模型（本地）
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL",
        "BAAI/bge-small-zh-v1.5"
    )
    # 集合名称
    collection_name: str = "agent_memory"
    # 最大召回条数
    top_k: int = 5
    # 记忆保留天数（-1为永久）
    retention_days: int = int(os.getenv("MEMORY_RETENTION_DAYS", "-1"))


class AgentConfig(BaseModel):
    """Agent 核心配置"""
    # Agent名称
    name: str = "桌面智能助手"
    # 系统提示词
    system_prompt: str = (
        "你是一个强大的本地桌面AI助手，名叫'小智'。"
        "你能够理解屏幕内容、执行桌面操作、管理文件、控制应用程序。"
        "你会记住用户的偏好和历史交互，并根据上下文提供个性化服务。"
        "执行任务时，请先分析任务，再一步步执行，并报告执行结果。"
    )
    # 最大规划步数
    max_steps: int = 15
    # 任务超时（秒）
    task_timeout: int = 120
    # 是否启用详细日志
    verbose: bool = True


class ScreenConfig(BaseModel):
    """屏幕操作配置"""
    # 截图保存目录
    screenshot_dir: str = str(SCREENSHOT_DIR)
    # 操作间隔（秒），防止误操作
    action_delay: float = 0.5
    # 鼠标移动时长
    mouse_duration: float = 0.3
    # 是否显示点击特效
    show_click_effect: bool = True


class AppConfig(BaseModel):
    """应用总配置"""
    vision: VisionConfig = VisionConfig()
    whisper: WhisperConfig = WhisperConfig()
    tts: TTSConfig = TTSConfig()
    memory: MemoryConfig = MemoryConfig()
    agent: AgentConfig = AgentConfig()
    screen: ScreenConfig = ScreenConfig()
    # Gradio服务端口
    ui_port: int = int(os.getenv("UI_PORT", "7861"))
    # 日志级别
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


# 全局配置实例
config = AppConfig()

