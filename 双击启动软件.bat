@echo off
cd /d "%~dp0"
chcp 65001 >nul

python -m pip install -r requirements.txt -q & python app.py
