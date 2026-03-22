@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
pip install gradio==4.42.0 gradio_client==0.9.0 huggingface_hub==0.23.4 -i https://pypi.tuna.tsinghua.edu.cn/simple/
if errorlevel 1 goto err
if not exist logs mkdir logs
if not exist data\gradio_tmp mkdir data\gradio_tmp
set HF_ENDPOINT=https://hf-mirror.com
python main.py > logs\run.log 2>&1
goto end
:err
echo install failed
:end
pause
