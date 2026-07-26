"""
Qt compatibility layer supporting PySide6 (preferred) and PyQt5 (fallback).
"""
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
