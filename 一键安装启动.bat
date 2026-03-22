@echo off
chcp 65001 >nul
title 桌面AI助手 - 一键安装启动
color 0A

cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║      桌面AI助手 一键安装启动脚本        ║
echo  ║   Qwen2.5-VL + Whisper + ChromaDB       ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ========== 检查Python ==========
echo [步骤 1/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [错误] 未检测到 Python！
    echo  请先安装 Python 3.10+：
    echo  https://www.python.org/downloads/
    echo  安装时请勾选 Add Python to PATH
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  %%v 检测通过
echo.

:: ========== 创建虚拟环境 ==========
echo [步骤 2/5] 准备虚拟环境...
if not exist "venv\Scripts\activate.bat" (
    echo  正在创建虚拟环境...
    python -m venv venv
    echo  虚拟环境创建完成
) else (
    echo  虚拟环境已存在，跳过
)
call venv\Scripts\activate.bat
echo  虚拟环境已激活
echo.

:: ========== 升级pip ==========
echo [步骤 3/5] 升级 pip...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/ -q
echo  pip 升级完成
echo.

:: ========== 安装PyTorch ==========
echo [步骤 4/5] 检查 PyTorch...
:: 在虚拟环境内检测（激活后才检测）
python -c "import torch" >nul 2>&1
if errorlevel 1 (
    echo  虚拟环境中未找到 PyTorch，尝试从系统环境复制依赖...
    echo  直接用 pip 安装（跳过pytorch.org，用清华源）...
    pip install torch torchvision -i https://pypi.tuna.tsinghua.edu.cn/simple/ -q
    echo  PyTorch 安装完成
) else (
    for /f "tokens=*" %%v in ('python -c "import torch; print(torch.__version__)"') do echo  PyTorch %%v 已就绪，跳过安装
)
echo.

:: ========== 安装项目依赖 ==========
echo [步骤 5/5] 安装项目依赖（首次约5-10分钟）...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ --quiet
echo  所有依赖安装完成
echo.

:: ========== 创建.env ==========
if not exist ".env" (
    if exist "env.example" (
        copy env.example .env >nul
        echo  已创建 .env 配置文件
    )
)

:: ========== 设置HF镜像 ==========
set HF_ENDPOINT=https://hf-mirror.com

echo.
echo  ════════════════════════════════════════════
echo  依赖安装完成！正在启动 AI Agent...
echo.
echo  首次运行会自动下载模型（约15GB），请耐心等待
echo  模型下载完成后浏览器将自动打开：
echo  http://localhost:7860
echo.
echo  按 Ctrl+C 可停止服务
echo  ════════════════════════════════════════════
echo.

python main.py

pause
