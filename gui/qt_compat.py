"""
Qt compatibility layer supporting PySide6 (preferred) and PyQt5 (fallback).
"""
import os
import sys

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Signal, Slot, QThread, Qt
    QT_LIB = "PySide6"
except ImportError:
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets
        from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot, QThread, Qt
        QT_LIB = "PyQt5"
    except ImportError:
        raise ImportError("未发现 PySide6 或 PyQt5，请执行: pip install PySide6 或 pip install PyQt5")

QApplication = QtWidgets.QApplication
QMainWindow = QtWidgets.QMainWindow
QDialog = QtWidgets.QDialog
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QGridLayout = QtWidgets.QGridLayout
QGroupBox = QtWidgets.QGroupBox
QPushButton = QtWidgets.QPushButton
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QTextEdit = QtWidgets.QTextEdit
QComboBox = QtWidgets.QComboBox
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QProgressBar = QtWidgets.QProgressBar
QFileDialog = QtWidgets.QFileDialog
QMessageBox = QtWidgets.QMessageBox
QTabWidget = QtWidgets.QTabWidget
QCheckBox = QtWidgets.QCheckBox
QGuiApplication = QtGui.QGuiApplication
QCursor = QtGui.QCursor
QIcon = QtGui.QIcon

class DropLineEdit(QLineEdit):
    """QLineEdit supporting Drag-and-Drop of files and directories."""
    file_dropped = Signal(str)

    def __init__(self, filter_type='any', parent=None):
        super().__init__(parent)
        self.filter_type = filter_type  # 'excel', 'dir', 'file', 'any'
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile().strip()
                p_lower = path.lower()
                if self.filter_type == 'excel' and (p_lower.endswith('.xlsx') or p_lower.endswith('.xls') or p_lower.endswith('.csv')):
                    event.acceptProposedAction()
                    return
                elif self.filter_type == 'dir' and (os.path.isdir(path) or os.path.isfile(path)):
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
                path = os.path.abspath(urls[0].toLocalFile().strip())
                if self.filter_type == 'dir' and os.path.isfile(path):
                    path = os.path.dirname(path)
                self.setText(path)
                self.file_dropped.emit(path)
                event.acceptProposedAction()

class DropTableWidget(QTableWidget):
    """QTableWidget subclass supporting drag-and-drop of Excel files and directories."""
    excel_dropped = Signal(str)
    dir_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile().strip()
                p_lower = path.lower()
                if p_lower.endswith('.xlsx') or p_lower.endswith('.xls') or p_lower.endswith('.csv') or os.path.isdir(path) or os.path.isfile(path):
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
                    self.excel_dropped.emit(path)
                    event.acceptProposedAction()
                elif os.path.isdir(path):
                    self.dir_dropped.emit(path)
                    event.acceptProposedAction()
                elif os.path.isfile(path):
                    self.dir_dropped.emit(os.path.dirname(path))
                    event.acceptProposedAction()


