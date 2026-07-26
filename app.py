#!/usr/bin/env python3
"""
跨平台 NGS & CRISPR 扩增子分析小工具 - 主入口
==============================================
支持: Windows (WSL2 后台桥接), macOS, Linux
"""

import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.qt_compat import QApplication
from gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
