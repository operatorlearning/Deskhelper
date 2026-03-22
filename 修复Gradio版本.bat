@echo off
chcp 65001 >nul
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo 统一安装匹配版本的 gradio + gradio_client...
pip install "gradio==4.42.0" "gradio_client==0.9.1" "huggingface_hub==0.23.4" -i https://pypi.tuna.tsinghua.edu.cn/simple/
echo 完成！
pause
