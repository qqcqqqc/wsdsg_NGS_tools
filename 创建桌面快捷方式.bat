@echo off
chcp 65001 >nul
title 创建桌面快捷方式

set "TARGET_DIR=%~dp0"
set "BAT_PATH=%TARGET_DIR%双击启动软件.bat"
set "ICON_PATH=%TARGET_DIR%assets\app_icon.ico"

powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), '宇宙无敌NGS tool-cql定制版.lnk')); $s.TargetPath='%BAT_PATH%'; $s.WorkingDirectory='%TARGET_DIR%'; $s.IconLocation='%ICON_PATH%'; $s.Save()"

echo ===================================================
echo   🎉 桌面快捷方式创建成功！
echo   快捷方式名称: 宇宙无敌NGS tool-cql定制版
echo   图标: 疯狂戴夫 Icon
echo ===================================================
echo.
pause
