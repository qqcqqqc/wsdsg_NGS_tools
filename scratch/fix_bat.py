bat1_content = """@echo off
chcp 65001 >nul
title 宇宙无敌NGS tool-cql定制版

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
""".replace("\n", "\r\n")

bat2_content = """@echo off
chcp 65001 >nul
title 创建桌面快捷方式

cd /d "%~dp0"

python create_shortcut.py

echo.
pause
""".replace("\n", "\r\n")

with open("双击启动软件.bat", "w", encoding="gbk") as f:
    f.write(bat1_content)

with open("创建桌面快捷方式.bat", "w", encoding="gbk") as f:
    f.write(bat2_content)

print("Rewritten bat files successfully!")
