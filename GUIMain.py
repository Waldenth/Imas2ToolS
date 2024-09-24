import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QIcon
from IMAS2ViewerUI import *
import operations

class IMASMainForm(QMainWindow, Ui_IMAS2ToolMainWindow):
    def __init__(self, parent=None):
        super(IMASMainForm, self).__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QIcon('resource/logo.ico'))
        # imas2 file data
        self.selected_file = {"fileInfo":None, "data":None}
        
        self.actionOpen_mpc.triggered.connect(lambda:operations.select_openfile(self,"mpc"))
        self.actionOpen_tsk.triggered.connect(lambda:operations.select_openfile(self,"tsk"))
        self.actionOpen_nut.triggered.connect(lambda:operations.select_openfile(self,"nut"))
 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    appForm = IMASMainForm()
    appForm.show()
    sys.exit(app.exec_())