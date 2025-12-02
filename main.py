# main.py

import sys
from PyQt5.QtWidgets import QApplication
from gui.app_controller import AppController

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 启动控制器，它负责加载 UI 和连接所有逻辑
    controller = AppController()
    controller.show()
    
    sys.exit(app.exec_())