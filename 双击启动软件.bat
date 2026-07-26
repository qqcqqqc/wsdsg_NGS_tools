@echo off
chcp 65001 >nul
title 🧬 NGS & CRISPR 扩增子测序分析小工具

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
