@echo off
chcp 65001 >nul
title 🧬 宇宙无敌NGS tool-cql定制版

:: 自动切换到当前 bat 文件所在目录，确保放在桌面快捷方式也能精准启动
cd /d "%~dp0"

echo ===================================================
echo   正在自动检查依赖并启动软件，请稍候...
echo ===================================================
echo.

python -m pip install -r requirements.txt -q
python app.py

if %errorlevel% neq 0 (
    echo.
    echo [错误] 启动失败！请确保电脑已安装 Python。
    pause
)
