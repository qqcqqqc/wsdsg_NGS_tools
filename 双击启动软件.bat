@echo off
cd /d "%~dp0"
chcp 65001 >nul

python -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); print('\U0001F61B \U0001F61C \U0001F92A \U0001F61D '*60)"

python app.py
