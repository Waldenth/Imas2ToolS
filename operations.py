from PyQt5.QtWidgets import  QFileDialog, QMenu, QMessageBox
from PyQt5.QtGui import QStandardItem
from PyQt5.QtCore import Qt
import mpc
import mpc.mpctool

def select_openfile(parent, extend_name="."):
    # Open file dialog and select a file
    
    filter = "All Files (*.*)"
    load_function = None
    if extend_name == "mpc":
        filter = "MPC Files (*.mpc)"
        load_function = mpc.mpctool.load_mpc
    elif extend_name == "tsk":
        filter = "TSK Files (*.tsk)"
    elif extend_name == "nut":
        filter = "NUT Files (*.nut)"
    
    file_path, _ = QFileDialog.getOpenFileName(parent, 'Open file', '', filter)
    if file_path:
        load_function(file_path)