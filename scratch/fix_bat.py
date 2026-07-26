bat1_content = """@echo off
chcp 65001 >nul
title 😜 宇宙无敌NGS tool-cql定制版

cd /d "%~dp0"

echo.
echo    😜 😜 😜 😜 😜 😜 😜 😜 😜 😜 😜 😜 😜 😜 😜
echo    ==============================================
echo     “歪？数据歪？不要慌！戴夫顶着锅盖来帮你了！”
echo     正在为您极速拉起 宇宙无敌NGS tool-cql定制版... 🚀
echo    ==============================================
echo.

python -m pip install -r requirements.txt -q
python app.py

if %errorlevel% neq 0 (
    echo.
    echo 😜 [崩溃了！] 启动失败！请确保电脑已安装 Python。
    pause
)
""".replace("\n", "\r\n")

with open("双击启动软件.bat", "w", encoding="utf-8-sig") as f:
    f.write(bat1_content)

print("Rewritten 双击启动软件.bat with UTF-8 BOM successfully!")
