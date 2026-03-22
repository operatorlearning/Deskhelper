@echo off
chcp 65001 >nul
cd /d "%~dp0"
call venv\Scripts\activate.bat
set HF_ENDPOINT=https://hf-mirror.com
python main.py > logs\run.log 2>&1
echo 运行结束，查看日志: logs\run.log
pause

