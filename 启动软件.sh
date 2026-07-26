#!/bin/bash
# 🧬 NGS & CRISPR 扩增子测序分析小工具 (macOS / Linux 一键启动脚本)

cd "$(dirname "$0")"

echo "==================================================="
echo "  正在自动检查依赖并启动软件 (macOS / Linux)..."
echo "==================================================="
echo ""

python3 -m pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt -q
python3 app.py || python app.py
