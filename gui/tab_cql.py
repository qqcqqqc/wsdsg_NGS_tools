import os
from gui.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTextEdit, QProgressBar, QFileDialog, QMessageBox, QThread, Signal, Slot
)
from core.cql_engine import run_cql_pipeline
from core.platform_runner import global_runner

class CQLWorkerThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int, int)
    finished_signal = Signal(bool, str, str)

    def __init__(self, excel_path: str, fastq_dir: str, output_dir: str, parent=None):
        super().__init__(parent)
        self.excel_path = excel_path
        self.fastq_dir = fastq_dir
        self.output_dir = output_dir
        self._is_stopped = False

    def run(self):
        try:
            demux_dir, crispresso_dir, be_summary = run_cql_pipeline(
                excel_path=self.excel_path,
                raw_fastq_dir=self.fastq_dir,
                output_dir=self.output_dir,
                log_callback=self._emit_log,
                progress_callback=self._emit_progress
            )
            self.finished_signal.emit(True, demux_dir, be_summary)
        except Exception as e:
            self._emit_log(f"\n[ERROR] CQL 一体化处理中断: {str(e)}\n")
            self.finished_signal.emit(False, "", "")

    def _emit_log(self, text: str):
        if not self._is_stopped:
            self.log_signal.emit(text)

    def _emit_progress(self, current: int, total: int):
        if not self._is_stopped:
            self.progress_signal.emit(current, total)

    def stop(self):
        self._is_stopped = True
        global_runner.kill_current_process()
        self.terminate()

class CQLDialog(QDialog):
    """
    Dedicated CQL All-in-One Demux & Analysis Dialog ("宇宙最帅CQL专属福利").
    Simplified inputs: Only requires Excel file and Raw FASTQ directory.
    Output directory is automatically placed alongside Raw FASTQ directory.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("宇宙最帅CQL专属福利")
        self.resize(800, 580)
        self.worker = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Config Box
        config_box = QGroupBox("宇宙最帅CQL专属福利", self)
        config_layout = QVBoxLayout(config_box)

        # 1. Excel Sheet Selection
        excel_layout = QHBoxLayout()
        excel_layout.addWidget(QLabel("拆分分析一体表 (Excel):"))
        self.txt_excel = QLineEdit(self)
        self.txt_excel.setPlaceholderText("选择包含 (样品名, 描述, 所在样品库, 索引序列1, 索引序列2, sg, 原始序列) 的 Excel 表格...")
        excel_layout.addWidget(self.txt_excel)
        btn_excel = QPushButton("浏览 Excel...", self)
        btn_excel.clicked.connect(self.browse_excel)
        excel_layout.addWidget(btn_excel)
        config_layout.addLayout(excel_layout)

        # 2. Raw FASTQ Dir Selection
        fq_layout = QHBoxLayout()
        fq_layout.addWidget(QLabel("Raw FASTQ 文件夹:"))
        self.txt_fastq = QLineEdit(self)
        self.txt_fastq.setPlaceholderText("选择包含原始测序文库 FASTQ 文件的目录...")
        fq_layout.addWidget(self.txt_fastq)
        btn_fq = QPushButton("选择 FASTQ 目录...", self)
        btn_fq.clicked.connect(self.browse_fastq_dir)
        fq_layout.addWidget(btn_fq)
        config_layout.addLayout(fq_layout)

        main_layout.addWidget(config_box)

        # Execution & Control Box
        exec_box = QGroupBox("运行控制与系统日志", self)
        exec_layout = QVBoxLayout(exec_box)

        ctrl_layout = QHBoxLayout()
        self.btn_run = QPushButton("GO!!", self)
        self.btn_run.setStyleSheet("font-weight: bold; font-size: 16px; background-color: #2e7d32; color: white; padding: 10px 28px;")
        self.btn_run.clicked.connect(self.start_cql_pipeline)
        ctrl_layout.addWidget(self.btn_run)

        self.btn_stop = QPushButton("停止", self)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_cql_pipeline)
        ctrl_layout.addWidget(self.btn_stop)

        exec_layout.addLayout(ctrl_layout)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        exec_layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit(self)
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(240)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc; font-family: Consolas, monospace;")
        exec_layout.addWidget(self.log_text)

        main_layout.addWidget(exec_box)

    def browse_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 CQL 一体化 Excel 表格", "", "Excel 文件 (*.xlsx)")
        if path:
            self.txt_excel.setText(path)

    def browse_fastq_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择 Raw FASTQ 目录")
        if path:
            self.txt_fastq.setText(path)

    def start_cql_pipeline(self):
        excel_path = self.txt_excel.text().strip()
        fastq_dir = self.txt_fastq.text().strip()

        if not excel_path or not os.path.exists(excel_path):
            QMessageBox.warning(self, "输入错误", "请选择有效的 CQL 一体化 Excel 信息表！")
            return

        if not fastq_dir or not os.path.exists(fastq_dir):
            QMessageBox.warning(self, "输入错误", "请选择包含原始 FASTQ 文件的目录！")
            return

        # Auto-place output directory in the same folder as raw FASTQ directory
        output_dir = os.path.join(fastq_dir, "CQL_Pipeline_Output")

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setValue(0)

        self.worker = CQLWorkerThread(
            excel_path=excel_path,
            fastq_dir=fastq_dir,
            output_dir=output_dir
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_cql_pipeline(self):
        if self.worker:
            self.worker.stop()
            global_runner.kill_current_process()
            self.append_log("\n[WARN] 用户已强行终止 CQL 一体化流水线，并强杀底层生信进程！\n")
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)

    @Slot(str)
    def append_log(self, text: str):
        self.log_text.append(text.rstrip())
        self.log_text.ensureCursorVisible()

    @Slot(int, int)
    def update_progress(self, current: int, total: int):
        if total > 0:
            val = int((current / total) * 100)
            self.progress_bar.setValue(val)

    @Slot(bool, str, str)
    def on_finished(self, success: bool, demux_dir: str, be_summary: str):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(
                self,
                "CQL 一体化完成",
                f"🎉 恭喜！CQL 专属拆分与分析流水线处理完成！\n\n"
                f"拆分 Fastq 存储于: {demux_dir}\n"
                f"分析汇总报表已生成！"
            )
        else:
            QMessageBox.critical(self, "运行中断", "CQL 一体化流水线出现异常或被强行停止！")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            global_runner.kill_current_process()
            event.accept()
