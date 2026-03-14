# main.py

import sys
from PyQt5.QtWidgets import QApplication
from gui.app_controller import AppController

if __name__ == "__main__":
    open_file_path = None
    if len(sys.argv) > 1:
        try_open_file = sys.argv[1]
        if try_open_file.lower().endswith('.mpc') \
            or try_open_file.lower().endswith('.nut') \
            or try_open_file.lower().endswith('.tsk') \
            or try_open_file.lower().endswith('.mot') \
            or try_open_file.lower().endswith('.s2d'):
            open_file_path = try_open_file

    app = QApplication(sys.argv)

    # 启动控制器，它负责加载 UI 和连接所有逻辑
    controller = AppController()
    controller.show()

    # 如果有传入 nut/mpc/tsk 文件，自动打开
    if open_file_path:
        file_type = open_file_path.split('.')[-1].lower()
        # 直接调用打开逻辑
        controller.handle_open_file(file_type = file_type, file_path = open_file_path)

    sys.exit(app.exec_())