import sys
import os
from gui.qt_compat import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QMessageBox, QDialog, QTextEdit, QT_LIB,
    QGuiApplication, Qt
)
from gui.tab_cql import CQLDialog
from gui.tab_demux import DemuxTab
from gui.tab_crispresso import CRISPRessoTab
from core.env_checker import check_environment

class EnvDiagnosticsDialog(QDialog):
    """
    Detailed Environment Diagnostics & One-Click Guided Setup Dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 后台生信环境诊断与一键配置指南")
        self.resize(720, 540)
        self.init_ui()
        self.refresh_diagnostics()

    def init_ui(self):
        layout = QVBoxLayout(self)

        lbl_title = QLabel("后台生信依赖环境检测状态", self)
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1976d2;")
        layout.addWidget(lbl_title)

        # Status cards text area (Dark background for crisp contrast against green checks)
        self.txt_status = QTextEdit(self)
        self.txt_status.setReadOnly(True)
        self.txt_status.setMaximumHeight(150)
        self.txt_status.setStyleSheet("background-color: #1e1e1e; color: #ffffff; font-size: 13px; font-family: Consolas, monospace;")
        layout.addWidget(self.txt_status)

        # One-Click Setup Script Section
        lbl_script_title = QLabel("💡 缺失环境一键配置脚本 (复制以下命令至 Windows PowerShell 中运行):", self)
        lbl_script_title.setStyleSheet("font-weight: bold; color: #333333; margin-top: 10px;")
        layout.addWidget(lbl_script_title)

        self.script_box = QTextEdit(self)
        self.script_box.setReadOnly(True)
        self.script_box.setStyleSheet("background-color: #1e1e1e; color: #76ff03; font-family: Consolas, monospace; font-size: 12px;")
        
        install_script = (
            "# 0. 如果 Windows 尚未启用 WSL2，先在 Windows PowerShell (管理员) 中运行以下命令安装 WSL2:\n"
            "wsl --install\n"
            "# (安装完成后重启电脑，重新打开 PowerShell 运行后续命令)\n\n"
            "# 1. 打开 Windows PowerShell，输入 wsl 进入 Linux 环境:\n"
            "wsl\n\n"
            "# 2. 下载并安装 Miniconda (清华源镜像):\n"
            "cd ~\n"
            "wget https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh && bash miniconda.sh -b -p $HOME/miniconda3\n"
            "$HOME/miniconda3/bin/conda init bash && source ~/.bashrc\n\n"
            "# 3. 创建专属生信环境并安装 crispresso2 和 cutadapt:\n"
            "conda create -n ngs python=3.10 -y\n"
            "conda activate ngs\n"
            "conda install -c bioconda -c conda-forge crispresso2 cutadapt -y"
        )
        self.script_box.setPlainText(install_script)
        layout.addWidget(self.script_box)

        # Action Buttons
        btn_layout = QHBoxLayout()

        btn_copy = QPushButton("📋 一键复制 WSL 安装脚本", self)
        btn_copy.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 6px 14px;")
        btn_copy.clicked.connect(self.copy_script)
        btn_layout.addWidget(btn_copy)

        btn_recheck = QPushButton("🔄 重新检测环境", self)
        btn_recheck.clicked.connect(self.refresh_diagnostics)
        btn_layout.addWidget(btn_recheck)

        btn_close = QPushButton("关闭", self)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def refresh_diagnostics(self):
        env_res = check_environment()
        status_lines = []
        
        if env_res['wsl_available']:
            status_lines.append("✅ [WSL2 Linux 环境]: 已安装且运行正常")
        else:
            status_lines.append("❌ [WSL2 Linux 环境]: 未检测到，请先在 PowerShell 管理员模式中运行 'wsl --install' 并重启电脑")

        if env_res['cutadapt_installed']:
            msg = [m for m in env_res['messages'] if 'cutadapt' in m][0]
            status_lines.append(f"✅ [cutadapt 拆分工具]: {msg}")
        else:
            status_lines.append("❌ [cutadapt 拆分工具]: 未检测到，拆分功能将不可用")

        if env_res['crispresso_installed']:
            msg = [m for m in env_res['messages'] if 'CRISPResso' in m][0]
            status_lines.append(f"✅ [CRISPResso2 分析工具]: {msg}")
        else:
            status_lines.append("❌ [CRISPResso2 分析工具]: 未检测到，基因编辑分析功能将不可用")

        self.txt_status.setPlainText("\n".join(status_lines))

    def copy_script(self):
        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(self.script_box.toPlainText())
            QMessageBox.information(self, "复制成功", "安装脚本已成功复制到剪贴板！\n请粘贴至 Windows PowerShell 中回车运行。")
        except Exception as e:
            QMessageBox.warning(self, "复制失败", f"无法复制到剪贴板: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"跨平台 NGS & CRISPR 扩增子分析小工具 v2.2 ({QT_LIB})")
        self.resize(1150, 880)
        self.init_ui()
        self.run_env_check()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Header Environment Banner
        self.header_banner = QWidget(self)
        self.header_banner.setStyleSheet("background-color: #2b2b2b; border-radius: 4px; padding: 6px;")
        banner_layout = QHBoxLayout(self.header_banner)
        
        self.lbl_env_status = QLabel("正在诊断后台生信运行环境...", self)
        self.lbl_env_status.setStyleSheet("color: #ffffff; font-weight: bold;")
        banner_layout.addWidget(self.lbl_env_status)
        
        banner_layout.addStretch()
        
        btn_recheck = QPushButton("🔍 环境诊断与一键配置", self)
        btn_recheck.setStyleSheet("background-color: #00838f; color: white; font-weight: bold;")
        btn_recheck.clicked.connect(self.show_diagnostics_dialog)
        banner_layout.addWidget(btn_recheck)

        layout.addWidget(self.header_banner)

        # Main Tabs (Standard 2 Tabs)
        self.tabs = QTabWidget(self)
        self.tab_demux = DemuxTab(self)
        self.tab_crispresso = CRISPRessoTab(self)

        self.tabs.addTab(self.tab_demux, "🔀 FASTQ UDI 拆分")
        self.tabs.addTab(self.tab_crispresso, "🧬 CRISPResso2 基因编辑效率分析 (NHEJ/BE/HDR/PE)")

        layout.addWidget(self.tabs)

        # Footer Layout with Secret Easter Egg Button "宇宙最帅cql" at Bottom-Right Corner
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(5, 0, 5, 2)
        footer_layout.addStretch()

        self.btn_secret_cql = QPushButton("宇宙最帅cql", self)
        self.btn_secret_cql.setCursor(Qt.PointingHandCursor)
        self.btn_secret_cql.setStyleSheet("border: none; background: transparent; color: #777777; font-size: 10px; padding: 2px 4px;")
        self.btn_secret_cql.setToolTip("隐藏入口: 点击打开 CQL 专属拆分分析一体化")
        self.btn_secret_cql.clicked.connect(self.show_cql_dialog)
        footer_layout.addWidget(self.btn_secret_cql)

        layout.addLayout(footer_layout)

    def run_env_check(self):
        env_res = check_environment()
        
        if env_res['cutadapt_installed'] and env_res['crispresso_installed']:
            self.lbl_env_status.setText("环境状态: ✅ WSL2 / cutadapt / CRISPResso2 后台生信环境全部就绪！")
            self.lbl_env_status.setStyleSheet("color: #4caf50; font-weight: bold;")
        else:
            missing = []
            if not env_res['cutadapt_installed']: missing.append("cutadapt")
            if not env_res['crispresso_installed']: missing.append("CRISPResso2")
            self.lbl_env_status.setText(f"环境状态: ⚠️ 缺少生信组件 [{', '.join(missing)}]，点击右侧按钮查看一键配置指南")
            self.lbl_env_status.setStyleSheet("color: #ff9800; font-weight: bold;")

    def show_diagnostics_dialog(self):
        dialog = EnvDiagnosticsDialog(self)
        dialog.exec()
        self.run_env_check()

    def show_cql_dialog(self):
        dialog = CQLDialog(self)
        dialog.exec()
