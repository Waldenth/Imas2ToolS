import imageio
from PIL import Image
from PyQt5.QtWidgets import  QFileDialog, QMessageBox
import subprocess
import os
import pathlib

def png_to_dxt3dds(self):
    try:
        # Open file dialog and select a file
        file_path, _ = QFileDialog.getOpenFileName(self, 'Open file', '', 'PNG Files (*.png)')
        file_path = file_path.replace("/", "\\")
        folder = str(pathlib.Path(file_path).parent)
        filename_noext = str(pathlib.Path(file_path).stem)
        
        dds_file_path = folder + "\\" + filename_noext + ".dds"
        
        if file_path:
            nvdxtpath = os.getcwd() + "/bin/nvdxt.exe"
            command =  nvdxtpath + " -file " + file_path + " -output " + dds_file_path + " -rel_scale 1.0, 1.0 -nomipmap -dxt3"
            ret = subprocess.run(command, shell=True)
            if ret.returncode == 0:
                QMessageBox.information(self, "Success", "dds converted successfully.")
            else:
                QMessageBox.critical(self, "Error", "Failed to convert file.")
        else:
            QMessageBox.warning(self, "No Data", "No png to convert.")
    except Exception as e:
        QMessageBox.critical(self, "Error", f"Failed to convert file: {e}")
        
def dxt3dds_to_png(self):
    try:
        # Open file dialog and select a file
        file_path, _ = QFileDialog.getOpenFileName(self, 'Open file', '', 'DDS Files (*.dds)')
        file_path = file_path.replace("/", "\\")
        
        if file_path:
            ddstronkpath = os.getcwd() + "/bin/DDStronk.exe "
            command =  ddstronkpath + file_path
            ret = subprocess.run(command, shell=True)
            if ret.returncode == 0:
                QMessageBox.information(self, "Success", "png converted successfully.")
            else:
                QMessageBox.critical(self, "Error", "Failed to convert file.")
        else:
            QMessageBox.warning(self, "No Data", "No png to convert.")
    except Exception as e:
        QMessageBox.critical(self, "Error", f"Failed to convert file: {e}")
