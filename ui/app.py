# -*- coding: utf-8 -*-
"""
Gradio Web UI
提供美观的聊天界面，支持文字/图像/语音输入
"""

import sys
import os
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

:root {
  --bg-main:    #0a0c10;
  --bg-sidebar: #0d1117;
  --bg-card:    #161b22;
  --bg-hover:   #21262d;
  --border:     rgba(48, 54, 61, 0.8);
  --accent:     #79c0ff;
  --accent-glow:rgba(121, 192, 255, 0.3);
  --success:    #3fb950;
  --warning:    #d29922;
  --error:      #f85149;
  --text-primary:   #f0f6fc;
  --text-secondary: #8b949e;
  --text-tertiary:  #6e7681;
  --radius-lg:  16px;
  --radius-md:  12px;
  --radius-sm:  8px;
  --glass:      rgba(22, 27, 34, 0.7);
}

.gradio-container {
  background: var(--bg-main) !important;
  font-family: 'Inter', 'Noto Sans SC', sans-serif !important;
}

/* 布局容器 */
.main-layout {
  display: flex !important;
  gap: 0 !important;
  height: 100vh !important;
  max-width: 100% !important;
}

/* Header 优化 */
.agent-header {
  padding: 1.5rem 2rem;
  background: var(--glass);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 100;
}
.header-title-group h1 {
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(120deg, #79c0ff, #c9d1d9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 0.2rem;
}
.header-status-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.8rem;
  background: rgba(63, 185, 80, 0.1);
  border: 1px solid rgba(63, 185, 80, 0.2);
  border-radius: 20px;
  font-size: 0.75rem;
  color: var(--success);
  font-weight: 500;
}

/* Chatbot 消息样式优化 */
.chatbox {
  background: var(--bg-sidebar) !important;
  border-radius: var(--radius-lg) !important;
  border: 1px solid var(--border) !important;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.2) !important;
}
.message-wrap .message {
  border-radius: var(--radius-md) !important;
  padding: 1rem 1.25rem !important;
  margin-bottom: 1rem !important;
  max-width: 85% !important;
  line-height: 1.6 !important;
  font-size: 0.95rem !important;
}
.message.user {
  background: linear-gradient(135deg, #238636, #2ea043) !important;
  color: white !important;
  border: none !important;
  align-self: flex-end !important;
  box-shadow: 0 4px 12px rgba(46, 160, 67, 0.2) !important;
}
.message.bot {
  background: var(--bg-card) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border) !important;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
}

/* 按钮样式重塑 */
button.primary {
  background: var(--accent) !important;
  color: var(--bg-main) !important;
  border-radius: var(--radius-sm) !important;
  font-weight: 600 !important;
  box-shadow: 0 0 15px var(--accent-glow) !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
button.primary:hover {
  transform: translateY(-1px) scale(1.02) !important;
  background: #c9d1d9 !important;
  box-shadow: 0 0 25px var(--accent-glow) !important;
}
button.secondary {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  color: var(--text-secondary) !important;
}
button.secondary:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}

/* 输入框聚焦 */
textarea, input {
  background: var(--bg-sidebar) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
  transition: border-color 0.2s !important;
}
textarea:focus, input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-glow) !important;
}

/* 全屏毛玻璃背景 */
.gradio-container::before {
  content: '';
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: radial-gradient(circle at 10% 20%, rgba(121, 192, 255, 0.05) 0%, transparent 40%),
              radial-gradient(circle at 90% 80%, rgba(63, 185, 80, 0.03) 0%, transparent 40%);
  pointer-events: none;
  z-index: -1;
}

/* 滚动条美化 */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-tertiary); }

/* 浮窗模式适配 (窄屏) */
@media (max-width: 500px) {
  .gradio-container { min-width: 0 !important; width: 100% !important; }
  .agent-header { padding: 0.8rem 1rem !important; }
  .header-title-group h1 { font-size: 1.1rem !important; }
  .header-status-badge { display: none !important; }
  .main-tabs > div { padding: 0.5rem !important; }
  .input-row { flex-direction: column !important; }
  .panel { margin-bottom: 0.5rem !important; }
  .message-wrap .message { max-width: 95% !important; }
}
"""


def create_ui(agent=None):
    """
    创建 Gradio UI
    Args:
        agent: DesktopAgent 实例，None 则显示未连接状态
    """
    import gradio as gr
    import tempfile
    import os
    # 设置Gradio临时目录为项目内，避免权限问题
    os.environ["GRADIO_TEMP_DIR"] = str(Path(__file__).parent.parent / "data" / "gradio_tmp")
    Path(os.environ["GRADIO_TEMP_DIR"]).mkdir(parents=True, exist_ok=True)

    # ---- 核心处理函数 ----

    def chat_fn(message, history, image_input, use_voice_output):
        """处理聊天消息"""
        if not message.strip() and image_input is None:
            return history, ""

        display_msg = message
        img = None
        if image_input is not None:
            display_msg = f"[图像] {message}" if message else "[图像分析请求]"
            try:
                from PIL import Image as PILImage
                img = PILImage.fromarray(image_input)
                logger.debug("图片输入已转换为 PIL Image")
            except Exception as e:
                logger.error(f"图片转换失败: {e}")
                img = image_input
                logger.debug(f"图片内容: {img}")
        history = history or []
        try:
            if agent is None:
                reply = "⚠️ Agent 未加载。请先运行 main.py 启动服务。"
            else:
                reply = agent.chat(message, image=img)
                if use_voice_output:
                    agent.speak(reply)
        except Exception as e:
            reply = f"❌ 错误: {e}"
            logger.error(f"聊天处理错误: {e}")

        # 保证 history 为消息字典列表
        if not isinstance(history, list):
            history = []
        # 只保留消息字典
        history = [msg for msg in history if isinstance(msg, dict) and "role" in msg and "content" in msg]
        history.append({"role": "user", "content": display_msg})
        history.append({"role": "assistant", "content": reply})
        return history, ""

    def screenshot_fn():
        """截图并分析"""
        try:
            if agent is None:
                return None, "Agent 未加载"
            img, path = agent.screen.capture_full(save=True)
            import numpy as np
            analysis = agent.analyze_current_screen()
            return np.array(img), analysis
        except Exception as e:
            return None, f"错误: {e}"

    def voice_input_fn():
        """录音并识别"""
        try:
            if agent is None:
                return "Agent 未加载"
            text = agent.transcribe_voice()
            return text
        except Exception as e:
            return f"录音错误: {e}"

    def get_status_fn():
        """获取Agent状态"""
        if agent is None:
            return "🔴 Agent 未连接"
        status = agent.get_status()
        parts = [
            f"🟢 {status['name']}",
            f"💬 对话: {status['short_term_count']}条",
            f"🧠 记忆: {status['memory_count']}条",
            f"🔧 工具: {status['tools_count']}个",
            f"👁 视觉: {'已加载' if status['vision_loaded'] else '待加载'}",
        ]
        return "  |  ".join(parts)

    def get_memories_fn():
        """获取所有记忆"""
        if agent is None:
            return "Agent 未加载"
        memories = agent.memory.get_all_memories()
        if not memories:
            return "暂无记忆"
        lines = []
        for m in memories:
            t = m["metadata"].get("type", "general")
            ts = m["metadata"].get("timestamp", "")[:16]
            lines.append(f"[{t}] {ts}\n{m['content']}\n")
        return "\n---\n".join(lines)

    def clear_memory_fn():
        if agent:
            agent.memory.clear_short_term()
        return "✅ 短期记忆已清空"

    def execute_task_fn(task_text):
        """直接执行任务"""
        if not task_text.strip():
            return "请输入任务描述"
        try:
            if agent is None:
                return "Agent 未加载"
            agent._load_llm()
            plan = agent.planner.plan(task_text)
            result = agent.executor.execute_plan(plan)
            return result["summary"]
        except Exception as e:
            return f"任务执行错误: {e}"

    # ---- 构建 UI ----
    with gr.Blocks(title="桌面AI助手") as demo:

        # Header
        gr.HTML(f"""
        <div class="agent-header">
          <div class="header-title-group">
            <h1>⬡ 桌面智能助手</h1>
            <p style="color: var(--text-tertiary); font-size: 0.8rem;">Qwen2.5-VL · Whisper · ChromaDB · LangChain — 本地运行</p>
          </div>
          <div class="header-status-badge">
            <span class="status-dot"></span>
            Agent 正常运行中
          </div>
        </div>
        """)

        # 主区域 Tabs
        with gr.Tabs(elem_classes=["main-tabs"]):

            # ---- Tab 1: 对话 ----
            with gr.Tab("💬 对话"):
                with gr.Row(equal_height=True):
                    with gr.Column(scale=4):
                        chatbot = gr.Chatbot(
                            label="",
                            height=520,
                            elem_classes=["chatbox"],
                            avatar_images=(None, "https://api.dicebear.com/7.x/bottts/svg?seed=agent"),
                            bubble_full_width=False,
                        )
                    with gr.Column(scale=1, min_width=200):
                        with gr.Group(elem_classes=["panel"]):
                            gr.Markdown("### 🛠 辅助工具")
                            voice_btn = gr.Button("🎤 语音输入", variant="secondary")
                            voice_output_cb = gr.Checkbox(label="🔊 语音播报回复", value=False)
                            clear_btn = gr.Button("🗑 清空对话", variant="secondary")
                            gr.Markdown("---")
                            status_info = gr.Textbox(
                                value=get_status_fn(),
                                label="系统状态",
                                lines=6,
                                interactive=False,
                                container=False,
                                elem_classes=["status-text-area"]
                            )

                with gr.Row(elem_classes=["input-row"]):
                    image_input = gr.Image(
                        label="视觉输入",
                        type="numpy",
                        scale=1,
                        height=100,
                    )
                    with gr.Column(scale=4):
                        msg_box = gr.Textbox(
                            placeholder="输入指令，例如：'帮我截个图' 或 '打开微信'...",
                            show_label=False,
                            lines=3,
                            container=False,
                        )
                        send_btn = gr.Button("发送指令 (Enter)", variant="primary")

                # 事件绑定
                send_btn.click(
                    chat_fn,
                    inputs=[msg_box, chatbot, image_input, voice_output_cb],
                    outputs=[chatbot, msg_box],
                )
                msg_box.submit(
                    chat_fn,
                    inputs=[msg_box, chatbot, image_input, voice_output_cb],
                    outputs=[chatbot, msg_box],
                )
                voice_btn.click(voice_input_fn, outputs=[msg_box])
                clear_btn.click(lambda: ([], ""), outputs=[chatbot, msg_box])

            # ---- Tab 2: 屏幕分析 ----
            with gr.Tab("🖥 屏幕分析"):
                with gr.Row(elem_classes=["input-row"]):
                    with gr.Column(scale=3):
                        screen_img = gr.Image(label="当前屏幕", type="numpy", elem_id="screen-view")
                    with gr.Column(scale=2):
                        with gr.Group(elem_classes=["panel"]):
                            screenshot_btn = gr.Button("📸 立即截图并分析", variant="primary", size="lg")
                            screen_analysis = gr.Textbox(
                                label="AI 分析详情",
                                lines=22,
                                interactive=False,
                                placeholder="分析结果将在此处显示..."
                            )
                screenshot_btn.click(screenshot_fn, outputs=[screen_img, screen_analysis])

            # ---- Tab 3: 任务执行 ----
            with gr.Tab("⚡ 自动化任务"):
                with gr.Row(elem_classes=["input-row"]):
                    with gr.Column(scale=2):
                        with gr.Group(elem_classes=["panel"]):
                            gr.Markdown("### 🚀 任务规划")
                            task_input = gr.Textbox(
                                label="任务描述",
                                placeholder="例如：帮我把桌面上的图片发送到微信群",
                                lines=5,
                            )
                            task_btn = gr.Button("开始执行", variant="primary", size="lg")
                    with gr.Column(scale=3):
                        with gr.Group(elem_classes=["panel"]):
                            gr.Markdown("### 📊 执行日志")
                            task_result = gr.Textbox(
                                label=None,
                                lines=18,
                                interactive=False,
                                placeholder="等待任务启动..."
                            )
                task_btn.click(execute_task_fn, inputs=[task_input], outputs=[task_result])

            # ---- Tab 4: 知识记忆 ----
            with gr.Tab("🧠 记忆管理"):
                with gr.Row(elem_classes=["input-row"]):
                    with gr.Column(scale=4):
                        mem_display = gr.Textbox(
                            label="长期记忆库 (ChromaDB)",
                            lines=20,
                            interactive=False,
                            value=get_memories_fn(),
                            elem_id="memory-content"
                        )
                    with gr.Column(scale=1):
                        with gr.Group(elem_classes=["panel"]):
                            gr.Markdown("### 🛠 操作")
                            refresh_mem_btn = gr.Button("🔄 刷新列表", variant="secondary")
                            clear_mem_btn = gr.Button("🗑 清空缓存", variant="secondary")
                            mem_msg = gr.Textbox(label="状态反馈", interactive=False)
                
                refresh_mem_btn.click(get_memories_fn, outputs=[mem_display])
                clear_mem_btn.click(clear_memory_fn, outputs=[mem_msg])

    return demo


if __name__ == "__main__":
    from config import config
    demo = create_ui(agent=None)
    demo.launch(
        server_port=config.ui_port,
        share=False,
        show_error=True,
        css=CSS,
    )

