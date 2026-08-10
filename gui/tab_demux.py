import os
from gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTextEdit, QTableWidget, QTableWidgetItem, QProgressBar,
    QFileDialog, QMessageBox, QCheckBox, QThread, Signal, Slot,
    DropLineEdit, DropTableWidget
)
from core.demux_engine import parse_excel_sample_sheet, run_demux_pipeline
from core.platform_runner import global_runner

class DemuxWorkerThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int, int)
    finished_signal = Signal(bool, list)

    def __init__(self, excel_path: str, fastq_dir: str, output_dir: str, error_rate: float, no_indels: bool, parent=None):
        super().__init__(parent)
        self.excel_path = excel_path
        self.fastq_dir = fastq_dir
        self.output_dir = output_dir
        self.error_rate = error_rate
        self.no_indels = no_indels
        self._is_stopped = False

    def run(self):
        try:
            generated = run_demux_pipeline(
                excel_path=self.excel_path,
                fastq_dir=self.fastq_dir,
                output_dir=self.output_dir,
                error_rate=self.error_rate,
                no_indels=self.no_indels,
                log_callback=self._emit_log,
                progress_callback=self._emit_progress
            )
            self.finished_signal.emit(True, generated)
        except Exception as e:
            self.log_signal.emit(f"\n[ERROR] 运行异常: {str(e)}\n")
            self.finished_signal.emit(False, [])

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

class DemuxTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.setAcceptDrops(True)
        self.init_ui()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = os.path.abspath(urls[0].toLocalFile().strip())
                p_lower = path.lower()
                if p_lower.endswith('.xlsx') or p_lower.endswith('.xls') or p_lower.endswith('.csv'):
                    self.txt_excel_path.setText(path)
                    event.acceptProposedAction()
                elif os.path.isdir(path):
                    if not self.txt_fastq_dir.text().strip():
                        self.txt_fastq_dir.setText(path)
                    else:
                        self.txt_output_dir.setText(path)
                    event.acceptProposedAction()
                elif os.path.isfile(path):
                    self.txt_fastq_dir.setText(os.path.dirname(path))
                    event.acceptProposedAction()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Path Selection Group
        path_box = QGroupBox("1. 输入与输出路径设置", self)
        path_layout = QVBoxLayout(path_box)

        # Excel sample sheet path
        excel_layout = QHBoxLayout()
        excel_layout.addWidget(QLabel("拆分信息表 (Excel):"))
        self.txt_excel_path = DropLineEdit(filter_type='excel', parent=self)
        self.txt_excel_path.setPlaceholderText("选择或直接拖入拆分信息.xlsx表格文件...")
        self.txt_excel_path.textChanged.connect(self.load_excel_table)
        excel_layout.addWidget(self.txt_excel_path)
        btn_browse_excel = QPushButton("浏览 Excel...", self)
        btn_browse_excel.clicked.connect(self.browse_excel)
        excel_layout.addWidget(btn_browse_excel)
        path_layout.addLayout(excel_layout)

        # FASTQ input dir
        fq_layout = QHBoxLayout()
        fq_layout.addWidget(QLabel("Raw FASTQ 文件夹:"))
        self.txt_fastq_dir = DropLineEdit(filter_type='dir', parent=self)
        self.txt_fastq_dir.setPlaceholderText("选择或直接拖入原始 FASTQ 文件夹...")
        fq_layout.addWidget(self.txt_fastq_dir)
        btn_browse_fq = QPushButton("选择 FASTQ 目录...", self)
        btn_browse_fq.clicked.connect(self.browse_fastq_dir)
        fq_layout.addWidget(btn_browse_fq)
        path_layout.addLayout(fq_layout)

        # Output dir
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("结果输出文件夹:"))
        self.txt_output_dir = DropLineEdit(filter_type='dir', parent=self)
        self.txt_output_dir.setPlaceholderText("选择或直接拖入拆分后样本文件的保存目录...")
        out_layout.addWidget(self.txt_output_dir)
        btn_browse_out = QPushButton("选择输出目录...", self)
        btn_browse_out.clicked.connect(self.browse_output_dir)
        out_layout.addWidget(btn_browse_out)
        path_layout.addLayout(out_layout)

        main_layout.addWidget(path_box)

        # 2. Sample Table Preview Group (Compact Narrow View)
        table_box = QGroupBox("2. 样本表配置与预览", self)
        table_layout = QVBoxLayout(table_box)

        self.table = DropTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "样品名", "描述", "所在样品库 (Pool)",
            "索引名1", "索引序列1 (idx1)", "索引名2", "索引序列2 (idx2)"
        ])
        self.table.setMaximumHeight(95)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.excel_dropped.connect(self.txt_excel_path.setText)
        self.table.dir_dropped.connect(self.txt_fastq_dir.setText)
        table_layout.addWidget(self.table)

        main_layout.addWidget(table_box)

        # 3. Parameters & Execution Console Group (Expanded Console Area for Real-time Speed & Progress)
        exec_box = QGroupBox("3. 拆分参数控制与实时控制台日志", self)
        exec_layout = QVBoxLayout(exec_box)

        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel("错配率 (Error Rate):"))
        self.txt_error_rate = QLineEdit("0.0", self)
        self.txt_error_rate.setMaximumWidth(60)
        params_layout.addWidget(self.txt_error_rate)

        self.chk_no_indels = QCheckBox("禁用 Indel 错配 (--no-indels)", self)
        self.chk_no_indels.setChecked(True)
        params_layout.addWidget(self.chk_no_indels)

        btn_help_demux = QPushButton("💡 参数说明", self)
        btn_help_demux.setStyleSheet("background-color: #0288d1; color: white; padding: 2px 8px;")
        btn_help_demux.clicked.connect(self.show_demux_help)
        params_layout.addWidget(btn_help_demux)

        params_layout.addStretch()

        self.btn_run = QPushButton("开始 UDI 拆分", self)
        self.btn_run.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #2e7d32; color: white; padding: 6px 16px;")
        self.btn_run.clicked.connect(self.start_demux)
        params_layout.addWidget(self.btn_run)

        self.btn_stop = QPushButton("停止", self)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_demux)
        params_layout.addWidget(self.btn_stop)

        exec_layout.addLayout(params_layout)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        exec_layout.addWidget(self.progress_bar)

        # Log Output Window (Expanded Height for Live Demux Speed & Progress)
        self.log_text = QTextEdit(self)
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(340)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc; font-family: Consolas, monospace;")
        exec_layout.addWidget(self.log_text)

        main_layout.addWidget(exec_box)

    def show_demux_help(self):
        msg = (
            "📖 FASTQ UDI 拆分参数说明：\n\n"
            "1. 错配率 (Error Rate, 默认 0.0):\n"
            "   允许在 UDI 双端 Index 序列中发生的碱基错配比例。\n"
            "   - 0.0: 要求 Index 100% 完美精准匹配（零容错，推荐）。\n"
            "   - 0.1: 允许每 10 个碱基中发生 1 个错配 (适合测序质量稍差情况)。\n\n"
            "2. 禁用 Indel 错配 (--no-indels, 默认勾选):\n"
            "   强制要求 Index 序列匹配只发生替换点突变，禁止发生插入/缺失导致的移码错位。\n"
            "   这样可以绝对保证 UDI 双端解交叠拆分的准确率，防止误拆分。兼具定向与非定向双端文库！"
        )
        QMessageBox.information(self, "拆分参数详细说明", msg)

    def browse_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择拆分信息 Excel 文件", "", "Excel 文件 (*.xlsx)")
        if path:
            self.txt_excel_path.setText(path)

    def browse_fastq_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择包含原始 FASTQ 文件的目录")
        if path:
            self.txt_fastq_dir.setText(path)

    def browse_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择拆分结果输出目录")
        if path:
            self.txt_output_dir.setText(path)

    def load_excel_table(self):
        path = self.txt_excel_path.text().strip()
        if not path or not os.path.exists(path):
            self.table.setRowCount(0)
            return

        try:
            lib_samples = parse_excel_sample_sheet(path)
            self.table.setRowCount(0)
            for lib, samples in lib_samples.items():
                for s in samples:
                    row_idx = self.table.rowCount()
                    self.table.insertRow(row_idx)
                    self.table.setItem(row_idx, 0, QTableWidgetItem(s['name']))
                    self.table.setItem(row_idx, 1, QTableWidgetItem(""))
                    self.table.setItem(row_idx, 2, QTableWidgetItem(lib))
                    self.table.setItem(row_idx, 3, QTableWidgetItem("idx1"))
                    self.table.setItem(row_idx, 4, QTableWidgetItem(s['idx1']))
                    self.table.setItem(row_idx, 5, QTableWidgetItem("idx2"))
                    self.table.setItem(row_idx, 6, QTableWidgetItem(s['idx2']))
            self.log_text.append(f"[INFO] 已自动从 Excel 导入预览 {self.table.rowCount()} 行样本条目。\n")
        except Exception as e:
            pass

    def start_demux(self):
        excel_path = self.txt_excel_path.text().strip()
        fastq_dir = self.txt_fastq_dir.text().strip()
        output_dir = self.txt_output_dir.text().strip()

        if not excel_path or not os.path.exists(excel_path):
            QMessageBox.warning(self, "参数错误", "请先选择有效的拆分信息 Excel 文件！")
            return

        if not fastq_dir or not os.path.exists(fastq_dir):
            QMessageBox.warning(self, "参数错误", "请先选择包含原始 FASTQ 文件的目录！")
            return

        if not output_dir:
            output_dir = os.path.join(fastq_dir, "demux_output")
            self.txt_output_dir.setText(output_dir)

        try:
            error_rate = float(self.txt_error_rate.text().strip())
        except ValueError:
            error_rate = 0.0
            self.txt_error_rate.setText("0.0")

        no_indels = self.chk_no_indels.isChecked()

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setValue(0)

        self.worker = DemuxWorkerThread(
            excel_path=excel_path,
            fastq_dir=fastq_dir,
            output_dir=output_dir,
            error_rate=error_rate,
            no_indels=no_indels
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_demux(self):
        if self.worker:
            self.worker.stop()
            self.append_log("\n[WARN] 用户手动强行终止拆分任务，正在停止所有底层子进程...\n")
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

    @Slot(bool, list)
    def on_finished(self, success: bool, files: list):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "拆分完成", f"恭喜！所有文库拆分处理完毕。\n共成功写出 {len(files)} 个样本 FASTQ.GZ 文件！")
        else:
            QMessageBox.critical(self, "拆分终止", "拆分过程中出现异常或被人工强行终止，请查看日志！")
