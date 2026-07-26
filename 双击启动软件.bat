@echo off
chcp 65001 >nul
title 宇宙无敌NGS tool-cql定制版

cd /d "%~dp0"

echo.
echo         .----------------.
echo        ^|   (==戴夫==)   ^|
echo         '----------------'
echo          /  o     O  \
echo         ^|     ___     ^|
echo          \   \___/   /
echo           '---\P/---'
echo     ==========================
echo      数据不要慌，戴夫带你飞！
echo     ==========================
echo.

python -m pip install -r requirements.txt -q
python app.py
