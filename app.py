import sys
import os
from gui.qt_compat import QApplication, QIcon
from gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "app_icon.png"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    # Use exec() if available, fallback to exec_() for legacy Qt
    if hasattr(app, 'exec'):
        sys.exit(app.exec())
    else:
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()
