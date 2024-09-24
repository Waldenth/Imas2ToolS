import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QTreeView,\
    QHBoxLayout, QDesktopWidget, QVBoxLayout
from PyQt5.QtGui import QIcon, QStandardItemModel
from IMAS2ViewerUI import *
import operations
import mpc.mpctool


class IMASMainForm(QMainWindow, Ui_IMAS2ToolMainWindow):
    def __init__(self, parent=None):
        super(IMASMainForm, self).__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QIcon('resource/logo.ico'))
        
        # Create the tree view
        self.treeView = QTreeView(self)
        self.verticalLayout.addWidget(self.treeView)
        # Create the model for the tree view
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['Folder Structure'])
        self.treeView.setModel(self.model)
        # Enable right-click context menu
        self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.open_context_menu)

        # imas2 file data
        self.opened_file = {"meta":{}, "data": None}
        
        self.export_funcs = {".mpc": self.mpc_export_file}
        self.replace_funcs = {".mpc": self.mpc_replace_file}
        
        
        self.actionOpen_mpc.triggered.connect(lambda:operations.select_openfile(self,".mpc"))
        self.actionOpen_tsk.triggered.connect(lambda:operations.select_openfile(self,".tsk"))
        self.actionOpen_nut.triggered.connect(lambda:operations.select_openfile(self,".nut"))
        self.actionSave_New_File.triggered.connect(lambda:operations.save_new_file(self))
    
    
    def center_window(self):
        qr = self.frameGeometry() 
        cp = QDesktopWidget().availableGeometry().center() 
        qr.moveCenter(cp)
        self.move(qr.topLeft())

IMASMainForm.open_context_menu = operations.open_context_menu
IMASMainForm.mpc_export_file = mpc.mpctool.export_file
IMASMainForm.mpc_replace_file = mpc.mpctool.replace_file

if __name__ == "__main__":
    app = QApplication(sys.argv)
    appForm = IMASMainForm()
    appForm.show()
    sys.exit(app.exec_())