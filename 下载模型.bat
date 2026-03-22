@echo off
chcp 65001 >nul
title 下载 Qwen2.5-VL 模型
color 0B

cd /d "%~dp0"
call venv\Scripts\activate.bat

echo.
echo  正在使用国内镜像下载 Qwen2.5-VL-7B 模型...
echo  文件共约 15GB，请保持网络连接，不要关闭此窗口
echo  支持断点续传，中断后重新运行可继续下载
echo.

set HF_ENDPOINT=https://hf-mirror.com
set HUGGINGFACE_HUB_VERBOSITY=info

python -c ^
"from huggingface_hub import snapshot_download; ^
print('开始下载...'); ^
snapshot_download(^
    repo_id='Qwen/Qwen2.5-VL-7B-Instruct', ^
    local_dir=None, ^
    ignore_patterns=['*.msgpack','*.h5','flax_model*','tf_model*'], ^
    resume_download=True^
); ^
print('下载完成！')"

echo.
echo  ============================================
echo  模型下载完成！现在可以运行 启动.bat 了
echo  ============================================
pause

