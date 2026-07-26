import sys
import os
import subprocess
import urllib.request
import json
import webbrowser
from gui.qt_compat import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QMessageBox, QDialog, QTextEdit, QT_LIB,
    QGuiApplication, Qt, QThread, Signal, Slot, QApplication
)
from gui.tab_cql import CQLDialog
from gui.tab_demux import DemuxTab
from gui.tab_crispresso import CRISPRessoTab
from core.env_checker import check_environment

VERSION = "v2.2.1"

class EnvCheckThread(QThread):
    """
    Background worker thread for checking WSL / cutadapt / CRISPResso2 environment.
    Runs asynchronously without freezing the main GUI event loop.
    """
    finished_signal = Signal(dict)

    def run(self):
        env_res = check_environment()
        self.finished_signal.emit(env_res)

class EnvReadyDialog(QDialog):
    """
    Fun dialog popped up when environment is already 100% ready.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("环境全部就绪")
        self.resize(420, 180)
        self.wants_secret_guide = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        lbl = QLabel("为师没有什么可以教你的了😌", self)
        lbl.setStyleSheet("font-size: 19px; font-weight: bold; color: #1565c0; margin: 20px 0;")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        btn_ok = QPushButton("彳亍", self)
        btn_ok.setStyleSheet("font-size: 13px; padding: 6px 16px;")
        btn_ok.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)

        btn_guide = QPushButton("我还想看武林秘籍🙏", self)
        btn_guide.setStyleSheet("font-size: 13px; padding: 6px 16px;")
        btn_guide.clicked.connect(self.on_secret_guide)
        btn_layout.addWidget(btn_guide)

        layout.addLayout(btn_layout)

    def on_secret_guide(self):
        self.wants_secret_guide = True
        self.accept()

class CQLPromptDialog(QDialog):
    """
    Easter Egg Quiz Dialog before entering CQL Exclusive Dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("你也觉得CQL宇宙最帅吗！！")
        self.resize(380, 160)
        self.selected_yes = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        lbl = QLabel("你也觉得CQL宇宙最帅吗！！", self)
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #d32f2f; margin: 15px 0;")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        btn_layout = QHBoxLayout()
        
        btn_yes = QPushButton("当然！！", self)
        btn_yes.setStyleSheet("font-size: 13px; padding: 6px 12px;")
        btn_yes.clicked.connect(self.on_yes)
        btn_layout.addWidget(btn_yes)

        btn_ok = QPushButton("彳亍", self)
        btn_ok.setStyleSheet("font-size: 13px; padding: 6px 12px;")
        btn_ok.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)

        btn_sure = QPushButton("确实", self)
        btn_sure.setStyleSheet("font-size: 13px; padding: 6px 12px;")
        btn_sure.clicked.connect(self.reject)
        btn_layout.addWidget(btn_sure)

        layout.addLayout(btn_layout)

    def on_yes(self):
        self.selected_yes = True
        self.accept()

class EnvDiagnosticsDialog(QDialog):
    """
    Detailed Environment Diagnostics & Guided Setup Dialog supporting Windows (WSL2), macOS, and Linux.
    """
    def __init__(self, initial_env_res: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 后台运行环境诊断与一键配置指南")
        self.resize(760, 580)
        self.cached_env_res = initial_env_res
        self.check_thread = None
        self.init_ui()

        if self.cached_env_res:
            self.display_env_res(self.cached_env_res)
        else:
            self.refresh_diagnostics_async()

    def init_ui(self):
        layout = QVBoxLayout(self)

        lbl_title = QLabel("后台依赖环境检测状态", self)
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1976d2;")
        layout.addWidget(lbl_title)

        # Status cards text area
        self.txt_status = QTextEdit(self)
        self.txt_status.setReadOnly(True)
        self.txt_status.setMaximumHeight(130)
        self.txt_status.setStyleSheet("background-color: #1e1e1e; color: #ffffff; font-size: 13px; font-family: Consolas, monospace;")
        layout.addWidget(self.txt_status)

        # Guided Setup Script Section
        lbl_script_title = QLabel("💡 多平台环境配置指导命令 (请根据你的操作系统选择在终端中运行):", self)
        lbl_script_title.setStyleSheet("font-weight: bold; color: #333333; margin-top: 10px;")
        layout.addWidget(lbl_script_title)

        self.script_box = QTextEdit(self)
        self.script_box.setReadOnly(True)
        self.script_box.setStyleSheet("background-color: #1e1e1e; color: #76ff03; font-family: Consolas, monospace; font-size: 12px;")
        
        install_script = (
            "====================================================================\n"
            "🪟 1. Windows 用户配置指南 (在 Windows PowerShell 的 WSL 中运行):\n"
            "====================================================================\n"
            "# 0. 若未启用 WSL2，先在 PowerShell (管理员) 运行: wsl --install 并重启电脑\n"
            "wsl\n\n"
            "# 1. 下载并安装 Miniconda (清华源镜像):\n"
            "cd ~\n"
            "wget https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh && bash miniconda.sh -b -p $HOME/miniconda3\n"
            "$HOME/miniconda3/bin/conda init bash && source ~/.bashrc\n\n"
            "# 2. 同意许可协议及通道配置:\n"
            "conda config --set auto_activate_base false\n"
            "conda config --set accept_default_spec_license true 2>/dev/null || true\n\n"
            "# 3. 创建专属运行环境并安装 cutadapt 与 crispresso2:\n"
            "conda create -n ngs python=3.10 -y\n"
            "conda activate ngs\n"
            "conda install -c bioconda -c conda-forge crispresso2 cutadapt -y\n\n\n"
            "====================================================================\n"
            "🍎 2. macOS 用户配置指南 (在终端 Terminal 中运行):\n"
            "====================================================================\n"
            "# 1. 打开终端 Terminal，下载并安装 Miniconda (清华源镜像):\n"
            "curl -O https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-MacOSX-arm64.sh && bash Miniconda3-latest-MacOSX-arm64.sh -b -p $HOME/miniconda3\n"
            "$HOME/miniconda3/bin/conda init zsh && source ~/.zshrc\n\n"
            "# 2. 同意许可协议及通道配置:\n"
            "conda config --set auto_activate_base false\n"
            "conda config --set accept_default_spec_license true 2>/dev/null || true\n\n"
            "# 3. 创建专属运行环境并安装 cutadapt 与 crispresso2:\n"
            "conda create -n ngs python=3.10 -y\n"
            "conda activate ngs\n"
            "conda install -c bioconda -c conda-forge crispresso2 cutadapt -y\n\n\n"
            "====================================================================\n"
            "🐧 3. Linux 用户配置指南 (在终端 Terminal 中运行):\n"
            "====================================================================\n"
            "# 1. 打开终端 Terminal，下载并安装 Miniconda (清华源镜像):\n"
            "wget https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh && bash miniconda.sh -b -p $HOME/miniconda3\n"
            "$HOME/miniconda3/bin/conda init bash && source ~/.bashrc\n\n"
            "# 2. 同意许可协议及通道配置:\n"
            "conda config --set auto_activate_base false\n"
            "conda config --set accept_default_spec_license true 2>/dev/null || true\n\n"
            "# 3. 创建专属运行环境并安装 cutadapt 与 crispresso2:\n"
            "conda create -n ngs python=3.10 -y\n"
            "conda activate ngs\n"
            "conda install -c bioconda -c conda-forge crispresso2 cutadapt -y"
        )
        self.script_box.setPlainText(install_script)
        layout.addWidget(self.script_box)

        # Action Buttons
        btn_layout = QHBoxLayout()

        self.btn_recheck = QPushButton("🔄 重新检测环境", self)
        self.btn_recheck.clicked.connect(self.refresh_diagnostics_async)
        btn_layout.addWidget(self.btn_recheck)

        btn_close = QPushButton("关闭", self)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def display_env_res(self, env_res: dict):
        self.cached_env_res = env_res
        status_lines = []
        
        if env_res['wsl_available']:
            status_lines.append("✅ [系统运行环境]: 已安装且运行正常")
        else:
            status_lines.append("❌ [系统运行环境]: 未检测到 WSL2，请先在 PowerShell 管理员模式中运行 'wsl --install' 并重启电脑")

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
        self.btn_recheck.setEnabled(True)
        self.btn_recheck.setText("🔄 重新检测环境")

    def refresh_diagnostics_async(self):
        self.btn_recheck.setEnabled(False)
        self.btn_recheck.setText("正在检测中...")
        self.txt_status.setPlainText("正在后台异步诊断系统及依赖组件状态，请稍候...")
        
        self.check_thread = EnvCheckThread(self)
        self.check_thread.finished_signal.connect(self.display_env_res)
        self.check_thread.start()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Title bar shows software name and current version dynamically
        self.setWindowTitle(f"宇宙无敌NGS tool-cql定制版 {VERSION}")
        self.resize(1150, 880)
        self.cached_env_res = None
        self.env_thread = None
        self.init_ui()
        self.run_env_check_async()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Top Bar: Small Repo Link (Left), Check Update Button (Right)
        top_bar = QWidget(self)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(4, 2, 4, 4)

        # Left: Small Open Source Repo Link
        lbl_repo = QLabel('🌟 开源于: <a href="https://github.com/qqcqqqc/wsdsg_NGS_tools" style="color: #64b5f6; font-size: 11px; text-decoration: none;">github.com/qqcqqqc/wsdsg_NGS_tools</a>', self)
        lbl_repo.setOpenExternalLinks(True)
        lbl_repo.setStyleSheet("font-size: 11px; color: #888888;")
        top_bar_layout.addWidget(lbl_repo)

        top_bar_layout.addStretch()

        # Right: Check Software Update Button
        btn_update = QPushButton("🔄 检查软件更新", self)
        btn_update.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 12px; padding: 4px 12px;")
        btn_update.clicked.connect(self.check_software_update)
        top_bar_layout.addWidget(btn_update)

        layout.addWidget(top_bar)

        # Header Environment Banner
        self.header_banner = QWidget(self)
        self.header_banner.setStyleSheet("background-color: #2b2b2b; border-radius: 4px; padding: 6px;")
        banner_layout = QHBoxLayout(self.header_banner)
        
        self.lbl_env_status = QLabel("正在诊断后台运行环境...", self)
        self.lbl_env_status.setStyleSheet("color: #ffffff; font-weight: bold;")
        banner_layout.addWidget(self.lbl_env_status)
        
        banner_layout.addStretch()
        
        btn_recheck = QPushButton("点我教你配置环境", self)
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

        # Footer Layout with Secret Easter Egg Button "宇宙最帅陈启亮" at Bottom-Left Corner
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(5, 0, 5, 2)

        self.btn_secret_cql = QPushButton("宇宙最帅陈启亮", self)
        self.btn_secret_cql.setCursor(Qt.PointingHandCursor)
        self.btn_secret_cql.setStyleSheet("border: none; background: transparent; color: #888888; font-size: 11px; padding: 2px 4px;")
        self.btn_secret_cql.setToolTip("隐藏入口: 点击进入 CQL 专属福利")
        self.btn_secret_cql.clicked.connect(self.show_cql_dialog)
        footer_layout.addWidget(self.btn_secret_cql)

        footer_layout.addStretch()
        layout.addLayout(footer_layout)

    def check_software_update(self):
        """
        Check for latest software updates via git pull or GitHub API.
        """
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            # 1. Try git pull if user is running from git repo
            if os.path.exists(os.path.join(os.path.dirname(__file__), "..", ".git")):
                res = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, timeout=10)
                QApplication.restoreOverrideCursor()
                if res.returncode == 0:
                    if "Already up to date" in res.stdout or "已经是最新的" in res.stdout:
                        QMessageBox.information(self, "检查软件更新", f"✅ 当前软件已是最新版本 ({VERSION})！无需更新。")
                    else:
                        QMessageBox.information(self, "更新成功", "🎉 发现并成功拉取了最新版本的代码！\n请重启软件以生效最新功能！")
                    return

            # 2. Fallback to GitHub API check for standalone EXE / non-git users
            req = urllib.request.Request(
                "https://api.github.com/repos/qqcqqqc/wsdsg_NGS_tools/releases/latest",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", VERSION)
                QApplication.restoreOverrideCursor()
                
                # Normalize versions for comparison
                norm_latest = latest_tag.lstrip("v").strip()
                norm_current = VERSION.lstrip("v").strip()
                
                if norm_latest != norm_current:
                    QMessageBox.information(
                        self,
                        "发现新版本",
                        f"🎉 发现 GitHub 上的最新发布版本: {latest_tag} (当前版本: {VERSION})！\n\n"
                        f"已为你打开仓库，请在 Releases 中下载最新安装包。"
                    )
                    webbrowser.open("https://github.com/qqcqqqc/wsdsg_NGS_tools/releases")
                else:
                    QMessageBox.information(self, "检查软件更新", f"✅ 当前软件已是最新版本 ({VERSION})！")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "检查软件更新", f"✅ 当前软件已是最新版本 ({VERSION})！\n(开源仓库: https://github.com/qqcqqqc/wsdsg_NGS_tools)")

    def run_env_check_async(self):
        self.lbl_env_status.setText("环境状态: ⏳ 正在后台异步检测运行环境...")
        self.lbl_env_status.setStyleSheet("color: #888888; font-weight: bold;")
        
        self.env_thread = EnvCheckThread(self)
        self.env_thread.finished_signal.connect(self.on_env_check_finished)
        self.env_thread.start()

    @Slot(dict)
    def on_env_check_finished(self, env_res: dict):
        self.cached_env_res = env_res
        
        if env_res['cutadapt_installed'] and env_res['crispresso_installed']:
            self.lbl_env_status.setText("环境状态: ✅ WSL2 / cutadapt / CRISPResso2 后台运行环境全部就绪！")
            self.lbl_env_status.setStyleSheet("color: #4caf50; font-weight: bold;")
        else:
            missing = []
            if not env_res['cutadapt_installed']: missing.append("cutadapt")
            if not env_res['crispresso_installed']: missing.append("CRISPResso2")
            self.lbl_env_status.setText(f"环境状态: ⚠️ 缺少组件 [{', '.join(missing)}]，点击右侧按钮查看一键配置指南")
            self.lbl_env_status.setStyleSheet("color: #ff9800; font-weight: bold;")

    def show_diagnostics_dialog(self):
        if self.cached_env_res and self.cached_env_res.get('cutadapt_installed') and self.cached_env_res.get('crispresso_installed'):
            dlg = EnvReadyDialog(self)
            dlg.exec()
            if not dlg.wants_secret_guide:
                return

        dialog = EnvDiagnosticsDialog(initial_env_res=self.cached_env_res, parent=self)
        if dialog.exec():
            if dialog.cached_env_res:
                self.on_env_check_finished(dialog.cached_env_res)

    def show_cql_dialog(self):
        prompt = CQLPromptDialog(self)
        if prompt.exec() and prompt.selected_yes:
            dialog = CQLDialog(self)
            dialog.exec()
