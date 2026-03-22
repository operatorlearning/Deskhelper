# -*- coding: utf-8 -*-
"""
语音交互模块
- STT: OpenAI Whisper 本地语音识别
- TTS: pyttsx3 离线合成 / edge-tts 微软在线合成
"""

import asyncio
import io
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger


class WhisperSTT:
    """Whisper 本地语音识别"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.model = None
        self._loaded = False

    def _load_model(self):
        if self._loaded:
            return
        logger.info(f"正在加载 Whisper {self.cfg.model_size} 模型...")
        import whisper
        self.model = whisper.load_model(
            self.cfg.model_size,
            device=self.cfg.device,
        )
        self._loaded = True
        logger.success(f"Whisper {self.cfg.model_size} 加载完成")

    def transcribe_file(self, audio_path: str) -> str:
        """
        识别音频文件
        Args:
            audio_path: 音频文件路径（wav/mp3/m4a等）
        Returns:
            识别文本
        """
        self._load_model()
        logger.debug(f"识别音频文件: {audio_path}")
        result = self.model.transcribe(
            audio_path,
            language=self.cfg.language,
            fp16=(self.cfg.device == "cuda"),
        )
        text = result["text"].strip()
        logger.info(f"语音识别结果: {text}")
        return text

    def transcribe_array(self, audio_array: np.ndarray) -> str:
        """
        识别numpy音频数组
        Args:
            audio_array: float32 numpy数组，采样率16000
        Returns:
            识别文本
        """
        self._load_model()
        result = self.model.transcribe(
            audio_array,
            language=self.cfg.language,
            fp16=(self.cfg.device == "cuda"),
        )
        return result["text"].strip()

    def record_and_transcribe(self) -> str:
        """
        录音并识别
        Returns:
            识别文本
        """
        import sounddevice as sd
        import soundfile as sf

        logger.info(f"开始录音，持续 {self.cfg.record_duration} 秒...")
        audio_data = sd.rec(
            int(self.cfg.record_duration * self.cfg.sample_rate),
            samplerate=self.cfg.sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        logger.info("录音完成，正在识别...")

        audio_array = audio_data.flatten()
        return self.transcribe_array(audio_array)

    def record_until_silence(
        self,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.5,
        max_duration: float = 30.0,
    ) -> str:
        """
        录音直到检测到静音
        Args:
            silence_threshold: 静音阈值（音量RMS）
            silence_duration: 静音持续多久后停止（秒）
            max_duration: 最大录音时长（秒）
        Returns:
            识别文本
        """
        import sounddevice as sd

        sample_rate = self.cfg.sample_rate
        chunk_size = int(sample_rate * 0.1)  # 100ms chunks
        max_chunks = int(max_duration / 0.1)
        silence_chunks = int(silence_duration / 0.1)

        audio_chunks = []
        silent_count = 0
        recording = True

        logger.info("开始录音（检测到静音后自动停止）...")

        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=chunk_size,
        ) as stream:
            chunk_count = 0
            while recording and chunk_count < max_chunks:
                chunk, _ = stream.read(chunk_size)
                audio_chunks.append(chunk.flatten())
                rms = np.sqrt(np.mean(chunk ** 2))
                if rms < silence_threshold:
                    silent_count += 1
                    if silent_count >= silence_chunks and len(audio_chunks) > silence_chunks:
                        recording = False
                else:
                    silent_count = 0
                chunk_count += 1

        logger.info("录音结束，正在识别...")
        audio_array = np.concatenate(audio_chunks)
        return self.transcribe_array(audio_array)


class TTSEngine:
    """TTS 语音合成引擎"""

    def __init__(self, cfg):
        self.cfg = cfg
        self._pyttsx3_engine = None
        self._lock = threading.Lock()

    def _get_pyttsx3(self):
        if self._pyttsx3_engine is None:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self.cfg.rate)
            engine.setProperty("volume", self.cfg.volume)
            # 尝试设置中文声音
            voices = engine.getProperty("voices")
            for voice in voices:
                if "chinese" in voice.name.lower() or "zh" in voice.id.lower():
                    engine.setProperty("voice", voice.id)
                    break
            self._pyttsx3_engine = engine
        return self._pyttsx3_engine

    def speak(self, text: str, save_path: Optional[str] = None) -> Optional[str]:
        """
        合成并播放语音
        Args:
            text: 要合成的文字
            save_path: 若提供则同时保存音频文件
        Returns:
            保存的音频路径（若save_path不为None）
        """
        if self.cfg.engine == "edge-tts":
            return self._speak_edge_tts(text, save_path)
        else:
            return self._speak_pyttsx3(text, save_path)

    def _speak_pyttsx3(self, text: str, save_path: Optional[str] = None) -> Optional[str]:
        """使用pyttsx3离线合成"""
        with self._lock:
            engine = self._get_pyttsx3()
            if save_path:
                engine.save_to_file(text, save_path)
                engine.runAndWait()
                logger.debug(f"TTS音频保存至: {save_path}")
                return save_path
            else:
                engine.say(text)
                engine.runAndWait()
                return None

    def _speak_edge_tts(self, text: str, save_path: Optional[str] = None) -> Optional[str]:
        """使用edge-tts在线合成（需要网络）"""
        import edge_tts

        if save_path is None:
            save_path = os.path.join(
                self.cfg.output_dir,
                f"tts_{int(time.time())}.mp3"
            )

        async def _synthesize():
            communicate = edge_tts.Communicate(text, self.cfg.edge_voice)
            await communicate.save(save_path)

        asyncio.run(_synthesize())
        logger.debug(f"edge-tts音频保存至: {save_path}")

        # 播放音频
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(save_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except ImportError:
            import subprocess
            subprocess.Popen(["start", save_path], shell=True)

        return save_path

    def speak_async(self, text: str):
        """异步非阻塞播放语音"""
        thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        thread.start()
        return thread

