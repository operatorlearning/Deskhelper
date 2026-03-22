# 桌面智能助手 - Desktop AI Agent

基于 **Qwen2.5-VL** 本地大模型的全功能桌面AI助手，支持屏幕理解、语音交互、跨应用自动化操作和持久化记忆系统。**完全本地运行，无需联网，保护隐私。**

## 核心功能

| 功能 | 技术 | 说明 |
|------|------|------|
| 屏幕理解 | Qwen2.5-VL + PaddleOCR | 截图分析、UI元素定位、文字识别 |
| 任务规划 | LangChain + Qwen2.5-VL | 自然语言→步骤序列自动分解 |
| 自动操作 | PyAutoGUI + PyWinAuto | 鼠标键盘控制、跨应用操作 |
| 语音交互 | Whisper STT + pyttsx3 TTS | 本地语音识别与合成 |
| 记忆系统 | ChromaDB + BGE嵌入 | 向量语义检索，跨会话持久记忆 |
| Web界面 | Gradio | 现代化聊天UI，支持多模态输入 |

## 项目结构

```
ai-agent/
├── main.py              # 主入口
├── config.py            # 统一配置
├── requirements.txt     # 依赖列表
├── core/
│   ├── agent.py         # 主Agent（协调所有模块）
│   ├── memory.py        # 记忆系统（ChromaDB + RAG）
│   ├── planner.py       # 任务规划器
│   └── executor.py      # 任务执行器 + 工具注册表
├── models/
│   ├── vision.py        # Qwen2.5-VL 视觉语言模型
│   ├── speech.py        # Whisper STT + TTS
│   └── ocr.py           # PaddleOCR
├── tools/
│   ├── screen.py        # 屏幕截图/录屏
│   ├── mouse_keyboard.py# 鼠标键盘控制
│   ├── file_ops.py      # 文件操作
│   └── app_control.py   # 跨应用操作
├── ui/
│   └── app.py           # Gradio Web界面
└── data/
    ├── memory/          # ChromaDB持久化
    ├── screenshots/     # 截图存储
    └── audio/           # 音频文件
```

## 快速开始

### 1. 环境要求

- Python 3.10+
- CUDA 11.8+ (推荐 NVIDIA GPU，显存 ≥ 16GB)
- Windows 10/11（跨应用操作依赖Windows API）

### 2. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装 PyTorch（CUDA版本，根据你的CUDA版本选择）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# 安装其他依赖
pip install -r requirements.txt
```

### 3. 下载模型

模型会在**首次运行时自动下载**到 HuggingFace 缓存目录。

也可手动提前下载（推荐）：

```bash
# 设置HuggingFace镜像（国内加速）
set HF_ENDPOINT=https://hf-mirror.com

# 下载 Qwen2.5-VL-7B
python -c "from transformers import Qwen2_5_VLForConditionalGeneration; Qwen2_5_VLForConditionalGeneration.from_pretrained('Qwen/Qwen2.5-VL-7B-Instruct')"

# 下载 Whisper medium
python -c "import whisper; whisper.load_model('medium')"

# 下载 BGE 嵌入模型
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"
```

### 4. 配置（可选）

创建 `.env` 文件自定义配置：

```env
# 如果已下载模型到本地，填写路径
VISION_MODEL_PATH=D:/models/Qwen2.5-VL-7B-Instruct

# 显存不足时启用4bit量化（牺牲少量精度，节省约50%显存）
USE_4BIT=true

# Whisper模型规格: tiny/base/small/medium/large
WHISPER_MODEL=medium

# Web UI端口
UI_PORT=7860

# 日志级别
LOG_LEVEL=INFO
```

### 5. 启动

```bash
python main.py
```

浏览器会自动打开 `http://localhost:7860`

## 使用示例

### 对话交互
```
用户: 帮我截图看看当前屏幕有什么
用户: 把桌面上的report.pdf发送到微信群"项目组"
用户: 在D盘下搜索所有名字包含"发票"的Excel文件
用户: 打开Chrome浏览器，访问百度
```

### 语音输入
点击「🎤 语音输入」按钮，对着麦克风说话，自动识别后填入输入框。

### 图像分析
上传截图或照片，配合文字提问，Qwen2.5-VL 会分析图像内容。

## 显存要求

| 模型 | 精度 | 显存需求 |
|------|------|----------|
| Qwen2.5-VL-7B | float16 | ~16GB |
| Qwen2.5-VL-7B | 4bit量化 | ~8GB |
| Qwen2.5-VL-3B | float16 | ~8GB |

> 无GPU时可将 `config.py` 中 `device` 改为 `"cpu"`，速度较慢但可运行。

## 注意事项

1. **微信自动化**：需要微信桌面版已登录，功能依赖UI坐标定位，不同版本可能有差异
2. **安全提醒**：`pyautogui.FAILSAFE=True`，将鼠标快速移到屏幕左上角可紧急停止所有操作
3. **首次加载**：视觉模型首次加载需要 1-3 分钟，请耐心等待

