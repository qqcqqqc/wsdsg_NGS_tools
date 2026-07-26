bat1_content = """@echo off
chcp 65001 >nul
title 😜 宇宙无敌NGS tool-cql定制版

cd /d "%~dp0"

echo.
echo 😛 😜 🤪 😝 正在启动 宇宙无敌NGS tool-cql定制版... 🚀
echo.

python -m pip install -r requirements.txt -q
python app.py
""".replace("\n", "\r\n")

with open("双击启动软件.bat", "w", encoding="utf-8-sig") as f:
    f.write(bat1_content)

print("Rewritten 双击启动软件.bat with 4 silly face emojis in single line successfully!")
