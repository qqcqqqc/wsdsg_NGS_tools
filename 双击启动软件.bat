@echo off
chcp 65001 >nul
title 😜 宇宙无敌NGS tool-cql定制版

cd /d "%~dp0"

echo.
echo 😛 😜 🤪 😝 正在启动 宇宙无敌NGS tool-cql定制版... 🚀
echo.

python -m pip install -r requirements.txt -q
python app.py
