import os
import re
from typing import Optional
import pandas as pd

from gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QProgressBar, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QCheckBox, QThread, Signal, Slot
)
from core.platform_runner import global_runner, win_to_wsl_path, is_windows
from core.crispresso_engine import (
    parse_crispresso_sample_sheet,
    run_crispresso_batch_pipeline
)

class DropLineEdit(QLineEdit):
    """QLineEdit supporting Drag and Drop of files and directories."""
    file_dropped = Signal(str)

    def __init__(self, filter_type='any', parent=None):
        super().__init__(parent)
        self.filter_type = filter_type  # 'excel', 'dir', 'file', 'any'
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if self.filter_type == 'excel' and (path.endswith('.xlsx') or path.endswith('.xls')):
                    event.acceptProposedAction()
                    return
                elif self.filter_type == 'dir' and os.path.isdir(path):
                    event.acceptProposedAction()
                    return
                elif self.filter_type in ['file', 'any'] and os.path.exists(path):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = os.path.abspath(urls[0].toLocalFile())
                self.setText(path)
                self.file_dropped.emit(path)
                event.acceptProposedAction()

class DropTableWidget(QTableWidget):
    """QTableWidget subclass supporting drag-and-drop of Excel files and FASTQ directories."""
    excel_dropped = Signal(str)
    dir_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if path.endswith('.xlsx') or path.endswith('.xls') or os.path.isdir(path):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = os.path.abspath(urls[0].toLocalFile())
                if path.endswith('.xlsx') or path.endswith('.xls'):
                    self.excel_dropped.emit(path)
                    event.acceptProposedAction()
                elif os.path.isdir(path):
                    self.dir_dropped.emit(path)
                    event.acceptProposedAction()

class CRISPRessoBatchWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int, int)
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        excel_path: str,
        fastq_dir: str,
        output_dir: str,
        mode: str,
        quant_window: int,
        cleavage_offset: int,
        min_read_qual: int = 30,
        exclude_left: int = 15,
        exclude_right: int = 15,
        plot_window: int = 20,
        parent=None
    ):
        super().__init__(parent)
        self.excel_path = excel_path
        self.fastq_dir = fastq_dir
        self.output_dir = output_dir
        self.mode = mode
        self.quant_window = quant_window
        self.cleavage_offset = cleavage_offset
        self.min_read_qual = min_read_qual
        self.exclude_left = exclude_left
        self.exclude_right = exclude_right
        self.plot_window = plot_window
        self._is_stopped = False

    def run(self):
        try:
            dirs, summary_excel = run_crispresso_batch_pipeline(
                excel_path=self.excel_path,
                fastq_dir=self.fastq_dir,
                output_dir=self.output_dir,
                mode=self.mode,
                quant_window=self.quant_window,
                cleavage_offset=self.cleavage_offset,
                min_read_qual=self.min_read_qual,
                exclude_left=self.exclude_left,
                exclude_right=self.exclude_right,
                plot_window=self.plot_window,
                log_callback=self._emit_log,
                progress_callback=self._emit_progress
            )
            if dirs:
                self.finished_signal.emit(True, summary_excel)
            else:
                self.finished_signal.emit(False, "")
        except Exception as e:
            self._emit_log(f"\n[ERROR] 批量分析运行异常: {str(e)}\n")
            self.finished_signal.emit(False, "")

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

class CRISPRessoSingleWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        r1_path: str,
        r2_path: str,
        amplicon: str,
        guide: str,
        mode: str,
        hdr_donor: str,
        output_dir: str,
        quant_window: int = 10,
        cleavage_offset: int = -3,
        min_read_qual: int = 30,
        exclude_left: int = 15,
        exclude_right: int = 15,
        plot_window: int = 20,
        parent=None
    ):
        super().__init__(parent)
        self.r1_path = os.path.abspath(r1_path)
        self.r2_path = os.path.abspath(r2_path) if r2_path else ""
        self.amplicon = amplicon.upper().strip()
        self.guide = guide.upper().strip()
        self.mode = mode
        self.hdr_donor = hdr_donor.upper().strip()
        self.output_dir = os.path.abspath(output_dir)
        self.quant_window = quant_window
        self.cleavage_offset = cleavage_offset
        self.min_read_qual = min_read_qual
        self.exclude_left = exclude_left
        self.exclude_right = exclude_right
        self.plot_window = plot_window
        self._is_stopped = False

    def run(self):
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            
            cmd = ["CRISPResso", "--fastq_r1", win_to_wsl_path(self.r1_path) if is_windows() else self.r1_path]
            if self.r2_path:
                cmd.extend(["--fastq_r2", win_to_wsl_path(self.r2_path) if is_windows() else self.r2_path])
                
            if self.guide:
                sg_l = len(self.guide)
                required_half_w = max(sg_l + self.cleavage_offset + 10, 15 - self.cleavage_offset)
                calc_plot_win = 2 * required_half_w
                plot_win_arg = max(self.plot_window, calc_plot_win)

                required_quant_half = max(sg_l + self.cleavage_offset + 5, 12 - self.cleavage_offset)
                quant_win_arg = max(self.quant_window, required_quant_half)
            else:
                plot_win_arg = self.plot_window
                quant_win_arg = self.quant_window

            cmd.extend([
                "--amplicon_seq", self.amplicon,
                "--guide_seq", self.guide,
                "--output_folder", win_to_wsl_path(self.output_dir) if is_windows() else self.output_dir,
                "--quantification_window_size", str(quant_win_arg),
                "--cleavage_offset", str(self.cleavage_offset),
                "--min_average_read_quality", str(self.min_read_qual),
                "--exclude_bp_from_left", str(self.exclude_left),
                "--exclude_bp_from_right", str(self.exclude_right),
                "--plot_window_size", str(plot_win_arg)
            ])
            
            if self.mode == "Base Editing (BE)":
                cmd.append("--base_editor_output")
            elif self.mode in ["HDR", "Prime Editing (PE)"] and self.hdr_donor:
                cmd.extend(["--expected_hdr_amplicon_seq", self.hdr_donor])
                
            self._emit_log("=" * 60 + "\n")
            self._emit_log(f"  CRISPResso2 单样本分析启动 [{self.mode} 模式]\n")
            self._emit_log("=" * 60 + "\n")
            self._emit_log(f"[INFO] R1: {self.r1_path}\n")
            if self.r2_path:
                self._emit_log(f"[INFO] R2: {self.r2_path}\n")
            self._emit_log(f"[INFO] Amplicon: {self.amplicon}\n")
            self._emit_log(f"[INFO] sgRNA:    {self.guide}\n")
            
            ret_code, out_text = global_runner.run_cmd(cmd, log_callback=self._emit_log)
            
            if ret_code == 0:
                self._emit_log("\n[OK] CRISPResso2 分析顺利完成！\n")
                self.finished_signal.emit(True, self.output_dir)
            else:
                self._emit_log(f"\n[FAIL] CRISPResso2 执行失败 (Exit code: {ret_code})\n")
                self.finished_signal.emit(False, "")
                
        except Exception as e:
            self._emit_log(f"\n[ERROR] 运行异常: {str(e)}\n")
            self.finished_signal.emit(False, "")

    def _emit_log(self, text: str):
        if not self._is_stopped:
            self.log_signal.emit(text)

    def stop(self):
        self._is_stopped = True
        global_runner.kill_current_process()
        self.terminate()

class CRISPRessoTab(QWidget):
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
                    self.txt_batch_excel.setText(path)
                    event.acceptProposedAction()
                elif os.path.isdir(path):
                    if not self.txt_batch_fq.text().strip():
                        self.txt_batch_fq.setText(path)
                    else:
                        self.txt_output_dir.setText(path)
                    event.acceptProposedAction()
                elif os.path.isfile(path):
                    if not self.txt_r1.text().strip():
                        self.txt_r1.setText(path)
                    elif not self.txt_r2.text().strip():
                        self.txt_r2.setText(path)
                    else:
                        self.txt_batch_fq.setText(os.path.dirname(path))
                    event.acceptProposedAction()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Mode Selection Header
        header_box = QGroupBox("模式与运行配置", self)
        header_layout = QHBoxLayout(header_box)

        header_layout.addWidget(QLabel("编辑分析类型:"))
        self.combo_edit_type = QComboBox(self)
        self.combo_edit_type.addItems(["Base Editing (BE)", "NHEJ", "HDR / Prime Editing (PE)"])
        self.combo_edit_type.currentTextChanged.connect(self.on_edit_type_changed)
        header_layout.addWidget(self.combo_edit_type)

        header_layout.addWidget(QLabel("运行模式:"))
        self.combo_run_mode = QComboBox(self)
        self.combo_run_mode.addItems(["📊 批量表格分析模式 (推荐)", "⚡ 单样本快速测试模式"])
        self.combo_run_mode.currentIndexChanged.connect(self.toggle_run_mode_view)
        header_layout.addWidget(self.combo_run_mode)

        header_layout.addStretch()
        main_layout.addWidget(header_box)

        # Advanced Optional Parameters Box
        adv_box = QGroupBox("绘图与定量扩展参数 (默认推荐无需修改)", self)
        adv_layout = QHBoxLayout(adv_box)

        adv_layout.addWidget(QLabel("上下游扩展侧翼(bp):"))
        self.txt_flank = QLineEdit("10", self)
        self.txt_flank.setMaximumWidth(40)
        self.txt_flank.setToolTip("以完整 sgRNA 序列为中心，向 5' 上游和 3' 下游各额外扩展的 bp 范围（默认上下游各 10bp，全 sgRNA 动态包容）。")
        adv_layout.addWidget(self.txt_flank)

        adv_layout.addWidget(QLabel("切割偏移:"))
        self.txt_offset = QLineEdit("-3", self)
        self.txt_offset.setMaximumWidth(40)
        self.txt_offset.setToolTip("切割位点偏移量（SpCas9 默认 -3，即 PAM 上游 3bp 处切割）。")
        adv_layout.addWidget(self.txt_offset)

        adv_layout.addWidget(QLabel("最小质量分(Q30):"))
        self.txt_min_qual = QLineEdit("30", self)
        self.txt_min_qual.setMaximumWidth(40)
        adv_layout.addWidget(self.txt_min_qual)

        adv_layout.addWidget(QLabel("左引物屏蔽(bp):"))
        self.txt_ex_left = QLineEdit("15", self)
        self.txt_ex_left.setMaximumWidth(40)
        adv_layout.addWidget(self.txt_ex_left)

        adv_layout.addWidget(QLabel("右引物屏蔽(bp):"))
        self.txt_ex_right = QLineEdit("15", self)
        self.txt_ex_right.setMaximumWidth(40)
        adv_layout.addWidget(self.txt_ex_right)

        btn_help_params = QPushButton("💡 参数说明", self)
        btn_help_params.setStyleSheet("background-color: #0288d1; color: white; padding: 2px 8px;")
        btn_help_params.clicked.connect(self.show_parameter_help)
        adv_layout.addWidget(btn_help_params)

        adv_layout.addStretch()
        main_layout.addWidget(adv_box)

        # View A: Batch Mode Box (Compact Preview Table View)
        self.batch_box = QGroupBox("批量样本分析配置与表格预览", self)
        batch_layout = QVBoxLayout(self.batch_box)

        excel_layout = QHBoxLayout()
        excel_layout.addWidget(QLabel("分析信息表 (Excel):"))
        self.txt_batch_excel = DropLineEdit(filter_type='excel', parent=self)
        self.txt_batch_excel.setPlaceholderText("选择或直接将 Excel 分析表拖入此处 (*.xlsx)...")
        self.txt_batch_excel.textChanged.connect(self.load_batch_excel)
        excel_layout.addWidget(self.txt_batch_excel)
        btn_browse_excel = QPushButton("浏览 Excel...", self)
        btn_browse_excel.clicked.connect(self.browse_batch_excel)
        excel_layout.addWidget(btn_browse_excel)
        batch_layout.addLayout(excel_layout)

        fq_layout = QHBoxLayout()
        fq_layout.addWidget(QLabel("FASTQ 文件夹:"))
        self.txt_batch_fq = DropLineEdit(filter_type='dir', parent=self)
        self.txt_batch_fq.setPlaceholderText("选择或直接将待分析 FASTQ 目录拖入此处...")
        fq_layout.addWidget(self.txt_batch_fq)
        btn_browse_fq = QPushButton("选择 FASTQ 目录...", self)
        btn_browse_fq.clicked.connect(self.browse_batch_fq_dir)
        fq_layout.addWidget(btn_browse_fq)
        batch_layout.addLayout(fq_layout)

        # Read-only compact table for previewing imported Excel sheet (narrowed height)
        self.table_batch = DropTableWidget(self)
        self.table_batch.setMaximumHeight(95)
        self.table_batch.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_batch.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_batch.excel_dropped.connect(self.txt_batch_excel.setText)
        self.table_batch.dir_dropped.connect(self.txt_batch_fq.setText)
        batch_layout.addWidget(self.table_batch)

        main_layout.addWidget(self.batch_box)

        # View B: Single Mode Box
        self.single_box = QGroupBox("单样本快速测试", self)
        single_layout = QVBoxLayout(self.single_box)

        r1_layout = QHBoxLayout()
        r1_layout.addWidget(QLabel("FASTQ R1 文件:"))
        self.txt_r1 = DropLineEdit(filter_type='file', parent=self)
        self.txt_r1.setPlaceholderText("选择或拖入 R1.fastq.gz...")
        r1_layout.addWidget(self.txt_r1)
        btn_r1 = QPushButton("浏览 R1", self)
        btn_r1.clicked.connect(self.browse_r1)
        r1_layout.addWidget(btn_r1)
        single_layout.addLayout(r1_layout)

        r2_layout = QHBoxLayout()
        r2_layout.addWidget(QLabel("FASTQ R2 文件 (可选):"))
        self.txt_r2 = DropLineEdit(filter_type='file', parent=self)
        self.txt_r2.setPlaceholderText("选择或拖入 R2.fastq.gz (单端可留空)...")
        r2_layout.addWidget(self.txt_r2)
        btn_r2 = QPushButton("浏览 R2", self)
        btn_r2.clicked.connect(self.browse_r2)
        r2_layout.addWidget(btn_r2)
        single_layout.addLayout(r2_layout)

        single_layout.addWidget(QLabel("Amplicon 序列:"))
        self.txt_amplicon = QLineEdit(self)
        self.txt_amplicon.setPlaceholderText("例如: ATCGATCG...")
        single_layout.addWidget(self.txt_amplicon)

        single_layout.addWidget(QLabel("sgRNA 序列 (20nt, 不含 PAM):"))
        self.txt_guide = QLineEdit(self)
        self.txt_guide.setPlaceholderText("例如: GTCGATCG...")
        single_layout.addWidget(self.txt_guide)

        self.lbl_hdr = QLabel("预期 Donor 序列:")
        self.txt_hdr = QLineEdit(self)
        self.lbl_hdr.setVisible(False)
        self.txt_hdr.setVisible(False)
        single_layout.addWidget(self.lbl_hdr)
        single_layout.addWidget(self.txt_hdr)

        self.single_box.setVisible(False)
        main_layout.addWidget(self.single_box)

        # Execution & Output Console Box (Expanded Height for Console)
        exec_box = QGroupBox("运行控制与实时控制台日志", self)
        exec_layout = QVBoxLayout(exec_box)

        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("结果输出目录:"))
        self.txt_output_dir = DropLineEdit(filter_type='dir', parent=self)
        self.txt_output_dir.setPlaceholderText("选择或直接拖入结果保存目录...")
        out_layout.addWidget(self.txt_output_dir)
        btn_out = QPushButton("选择目录", self)
        btn_out.clicked.connect(self.browse_output_dir)
        out_layout.addWidget(btn_out)

        self.btn_run = QPushButton("开始分析", self)
        self.btn_run.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #1976d2; color: white; padding: 6px 16px;")
        self.btn_run.clicked.connect(self.start_analysis)
        out_layout.addWidget(self.btn_run)

        self.btn_stop = QPushButton("停止", self)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_analysis)
        out_layout.addWidget(self.btn_stop)

        exec_layout.addLayout(out_layout)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        exec_layout.addWidget(self.progress_bar)

        # Log Text Window (Expanded Height for Live Logs)
        self.log_text = QTextEdit(self)
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(340)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc; font-family: Consolas, monospace;")
        exec_layout.addWidget(self.log_text)

        main_layout.addWidget(exec_box)

        # Initialize table headers for default mode
        self.on_edit_type_changed(self.combo_edit_type.currentText())

    def show_parameter_help(self):
        msg = (
            "📖 CRISPResso2 参数详细说明：\n\n"
            "1. 上下游扩展侧翼 (Flanking Window, 默认 10bp):\n"
            "   系统会自动读取每个样本的真实 sgRNA 长度，并以 sgRNA 为中心向 5' 上游和 3' 下游各延伸 10bp 作为统一定量与绘图边界。\n\n"
            "2. 切割偏移 (Cleavage Offset, 默认 -3):\n"
            "   预计基因切割位点距离 sgRNA 末尾的偏移量。此参数需根据所使用的核酸酶类型决定：\n"
            "   • SpCas9 / ABE / CBE：默认 -3（即 PAM 上游 3 个碱基处切割）。\n"
            "   • 其他核酸酶（如 Cas12a/Cpf1 等）：需根据其特有的切割位点调整。\n"
            "   注意：修改切割偏移会直接改变切割中心判定，进而影响 NHEJ 的 wt_allele 及 3n 框移/Indel Reads 的统计结果！\n\n"
            "3. 最小质量分 (Min Read Quality, 默认 30):\n"
            "   低于此 Phred 质量分 (Q30) 的 Reads 将被自动过滤，表示 99.9% 准确率。\n\n"
            "4. 左/右引物屏蔽 (Exclude Left/Right, 默认 15):\n"
            "   屏蔽 Amplicon 两端 PCR 引物结合区的碱基，防止引物合成低质量错配影响编辑统计。"
        )
        QMessageBox.information(self, "参数详细说明", msg)

    def toggle_run_mode_view(self, idx: int):
        is_batch = (idx == 0)
        self.batch_box.setVisible(is_batch)
        self.single_box.setVisible(not is_batch)

    def on_edit_type_changed(self, mode_text: str):
        is_hdr = ("HDR" in mode_text or "PE" in mode_text)
        self.lbl_hdr.setVisible(is_hdr)
        self.txt_hdr.setVisible(is_hdr)

        if "BE" in mode_text:
            self.txt_batch_excel.setPlaceholderText("选择 BE 分析表 (包含列: 样品名, 描述, sg, 原始序列, 原始碱基, 修改后碱基)...")
            headers = ["样品名", "描述", "sgRNA (sg)", "原始扩增子序列 (Amplicon)", "原始碱基 (From)", "修改后碱基 (To)"]
        elif "HDR" in mode_text or "PE" in mode_text:
            self.txt_batch_excel.setPlaceholderText("选择 HDR/PE 分析表 (包含列: 样品名, 描述, sg, 原始序列, 供体序列)...")
            headers = ["样品名", "描述", "sgRNA (sg)", "原始扩增子序列 (Amplicon)", "供体/PE序列 (Donor)"]
        else: # NHEJ
            self.txt_batch_excel.setPlaceholderText("选择 NHEJ 分析表 (包含列: 样品名, 描述, sg, 原始序列)...")
            headers = ["样品名", "描述", "sgRNA (sg)", "原始扩增子序列 (Amplicon)"]

        self.table_batch.setColumnCount(len(headers))
        self.table_batch.setHorizontalHeaderLabels(headers)
        
        if self.txt_batch_excel.text().strip():
            self.load_batch_excel()

    def browse_batch_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择分析信息 Excel 表格", "", "Excel 文件 (*.xlsx)")
        if path:
            self.txt_batch_excel.setText(path)

    def browse_batch_fq_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择 FASTQ 目录")
        if path:
            self.txt_batch_fq.setText(path)

    def browse_r1(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 FASTQ R1 文件", "", "FASTQ 文件 (*.fq.gz *.fastq.gz *.fq *.fastq)")
        if path:
            self.txt_r1.setText(path)

    def browse_r2(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 FASTQ R2 文件", "", "FASTQ 文件 (*.fq.gz *.fastq.gz *.fq *.fastq)")
        if path:
            self.txt_r2.setText(path)

    def browse_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存结果的目录")
        if path:
            self.txt_output_dir.setText(path)

    def load_batch_excel(self):
        path = self.txt_batch_excel.text().strip()
        if not path or not os.path.exists(path):
            self.table_batch.setRowCount(0)
            return
        try:
            samples = parse_crispresso_sample_sheet(path)
            self.table_batch.setRowCount(0)
            mode_text = self.combo_edit_type.currentText()
            
            for s in samples:
                r = self.table_batch.rowCount()
                self.table_batch.insertRow(r)
                self.table_batch.setItem(r, 0, QTableWidgetItem(s['name']))
                self.table_batch.setItem(r, 1, QTableWidgetItem(s['desc']))
                self.table_batch.setItem(r, 2, QTableWidgetItem(s['sg']))
                self.table_batch.setItem(r, 3, QTableWidgetItem(s['amplicon']))
                
                if "BE" in mode_text:
                    self.table_batch.setItem(r, 4, QTableWidgetItem(s['base_from']))
                    self.table_batch.setItem(r, 5, QTableWidgetItem(s['base_to']))
                elif ("HDR" in mode_text or "PE" in mode_text) and self.table_batch.columnCount() >= 5:
                    self.table_batch.setItem(r, 4, QTableWidgetItem(s['donor']))
                    
            self.log_text.append(f"[INFO] 成功在表格中预览载入 {len(samples)} 行样本。\n")
        except Exception as e:
            pass

    def start_analysis(self):
        try:
            flank = int(self.txt_flank.text().strip())
            cleavage_offset = int(self.txt_offset.text().strip())
            min_read_qual = int(self.txt_min_qual.text().strip())
            exclude_left = int(self.txt_ex_left.text().strip())
            exclude_right = int(self.txt_ex_right.text().strip())
        except ValueError:
            flank = 10
            cleavage_offset = -3
            min_read_qual = 30
            exclude_left = 15
            exclude_right = 15

        quant_window = flank
        plot_window = 20 + 2 * flank

        output_dir = self.txt_output_dir.text().strip()
        mode = self.combo_edit_type.currentText()
        is_batch = (self.combo_run_mode.currentIndex() == 0)

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setValue(0)

        if is_batch:
            excel_path = self.txt_batch_excel.text().strip()
            fastq_dir = self.txt_batch_fq.text().strip()

            if not excel_path or not os.path.exists(excel_path):
                QMessageBox.warning(self, "输入错误", "请选择有效的分析信息 Excel 表格！")
                self.btn_run.setEnabled(True)
                self.btn_stop.setEnabled(False)
                return

            if not fastq_dir or not os.path.exists(fastq_dir):
                QMessageBox.warning(self, "输入错误", "请选择包含待分析 FASTQ 文件的目录！")
                self.btn_run.setEnabled(True)
                self.btn_stop.setEnabled(False)
                return

            if not output_dir:
                output_dir = os.path.join(fastq_dir, "CRISPResso_Batch_Output")
                self.txt_output_dir.setText(output_dir)

            self.worker = CRISPRessoBatchWorker(
                excel_path=excel_path,
                fastq_dir=fastq_dir,
                output_dir=output_dir,
                mode=mode,
                quant_window=quant_window,
                cleavage_offset=cleavage_offset,
                min_read_qual=min_read_qual,
                exclude_left=exclude_left,
                exclude_right=exclude_right,
                plot_window=plot_window
            )
            self.worker.log_signal.connect(self.append_log)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.start()
        else:
            r1 = self.txt_r1.text().strip()
            r2 = self.txt_r2.text().strip()
            amp = self.txt_amplicon.text().upper().strip()
            guide = self.txt_guide.text().upper().strip()

            if not r1 or not os.path.exists(r1):
                QMessageBox.warning(self, "输入错误", "请选择有效的 FASTQ R1 文件！")
                self.btn_run.setEnabled(True)
                self.btn_stop.setEnabled(False)
                return

            if not amp or not guide:
                QMessageBox.warning(self, "输入错误", "请填入 Amplicon 与 sgRNA 序列！")
                self.btn_run.setEnabled(True)
                self.btn_stop.setEnabled(False)
                return

            if not output_dir:
                output_dir = os.path.join(os.path.dirname(r1), "CRISPResso_Single_Output")
                self.txt_output_dir.setText(output_dir)

            self.worker = CRISPRessoSingleWorker(
                r1_path=r1,
                r2_path=r2,
                amplicon=amp,
                guide=guide,
                mode=mode,
                hdr_donor=self.txt_hdr.text().strip(),
                output_dir=output_dir,
                quant_window=quant_window,
                cleavage_offset=cleavage_offset,
                min_read_qual=min_read_qual,
                exclude_left=exclude_left,
                exclude_right=exclude_right,
                plot_window=plot_window
            )
            self.worker.log_signal.connect(self.append_log)
            self.worker.finished_signal.connect(self.on_single_finished)
            self.worker.start()

    def stop_analysis(self):
        if self.worker:
            self.worker.stop()
            global_runner.kill_current_process()
            self.append_log("\n[WARN] 用户已强行终止基因编辑分析任务，并彻底强杀后台 WSL 进程！\n")
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

    @Slot(bool, str)
    def on_finished(self, success: bool, summary_excel: str):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "批量分析完成", f"恭喜！所有样本 CRISPResso2 批量分析处理完毕。\n汇总结果已自动导出至:\n{summary_excel}")
        else:
            QMessageBox.critical(self, "分析中断", "批量分析过程中出现异常或被强行终止，请查看运行日志！")

    @Slot(bool, str)
    def on_single_finished(self, success: bool, out_dir: str):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "分析完成", f"CRISPResso2 分析已顺利完成！\n结果报告已存至:\n{out_dir}")
        else:
            QMessageBox.critical(self, "分析中断", "CRISPResso2 运行遇到错误，请检查运行日志！")
