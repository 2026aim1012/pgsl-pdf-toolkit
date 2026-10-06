import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel


def main() -> None:
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Offline PDF Toolkit")
    window.resize(1280, 720)
    window.setCentralWidget(QLabel("Hello, PDF Toolkit!", parent=window))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()