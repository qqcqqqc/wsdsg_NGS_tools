@echo off
chcp 65001 >nul
title 创建桌面快捷方式

cd /d "%~dp0"

python create_shortcut.py

echo.
pause
