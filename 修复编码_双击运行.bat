@echo off
chcp 65001 >nul
title 修复PowerShell编码

echo 正在修复 PowerShell UTF-8 编码...
echo.

:: 创建 WindowsPowerShell 目录
if not exist "%USERPROFILE%\Documents\WindowsPowerShell" (
    mkdir "%USERPROFILE%\Documents\WindowsPowerShell"
    echo 已创建目录: %USERPROFILE%\Documents\WindowsPowerShell
)

:: 写入 PowerShell Profile
set PROFILE_PATH=%USERPROFILE%\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1

echo [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 > "%PROFILE_PATH%"
echo $OutputEncoding = [System.Text.Encoding]::UTF8 >> "%PROFILE_PATH%"
echo chcp 65001 ^| Out-Null >> "%PROFILE_PATH%"

echo 配置文件已写入: %PROFILE_PATH%
echo.

:: 同时设置注册表，让cmd也默认UTF-8
reg add "HKCU\Console" /v "CodePage" /t REG_DWORD /d 65001 /f >nul 2>&1
echo 注册表 CodePage 已设置为 65001 (UTF-8)
echo.

echo ============================================
echo  修复完成！
echo  请关闭此窗口，然后完全退出并重启 Cursor
echo ============================================
echo.
pause


