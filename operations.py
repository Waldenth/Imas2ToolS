from PyQt5.QtWidgets import  QFileDialog, QMenu, QMessageBox
from PyQt5.QtGui import QStandardItem
from PyQt5.QtCore import Qt
import mpc
import mpc.mpctool
import pathlib

def save_new_file(self):
    try:
        default_filename = self.opened_file["meta"]["file_name"]
        new_file_path, _ = QFileDialog.getSaveFileName(self, 'Save As New File', default_filename, 'All Files (*)')
        if new_file_path:
            # 将 new_mpc_data 写入到指定的文件中
            with open(new_file_path, 'wb') as f_out:
                f_out.write(self.opened_file["data"])
            QMessageBox.information(self, "Success", f"File saved as {new_file_path}")
        else:
            QMessageBox.warning(self, "No Data", "No data to save.")
    except Exception as e:
        QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

def select_openfile(self, extend_name="."):
    # Open file dialog and select a file
    
    filter = "All Files (*.*)"
    load_function = None
    if extend_name == ".mpc":
        filter = "MPC Files (*.mpc)"
        load_function = mpc.mpctool.load_mpc
    elif extend_name == ".tsk":
        filter = "TSK Files (*.tsk)"
    elif extend_name == ".nut":
        filter = "NUT Files (*.nut)"
    
    file_path, _ = QFileDialog.getOpenFileName(self, 'Open file', '', filter)
    if file_path:
        with open(file_path,"rb") as f:
            self.opened_file["data"] = bytearray(f.read())
            file = pathlib.Path(file_path)
            self.opened_file["meta"].update({"file_path":file_path})
            self.opened_file["meta"].update({"file_name":file.name})
            self.opened_file["meta"].update({"extension_name":file.suffix})
            
            self.opened_file["meta"].update(load_function(self.opened_file["data"]))
            fresh_tree_view(self)


def fresh_tree_view(self):
    file_path = self.opened_file['meta']['file_path']
    self.fileInfoLabel.setText(f"File: {file_path}")
    # Clear the current tree view
    self.model.clear()
    self.model.setHorizontalHeaderLabels(['Folder Structure'])
    
    # Repopulate the tree view with new data
    populate_tree(self, self.opened_file["meta"]["subfiles_info"])
    self.treeView.expandAll()
    
    
def populate_tree(self, subfiles_info):
    # Root item of the model
    rootItem = self.model.invisibleRootItem()
    # Dictionary to hold folder items for easy access
    folder_dict = {}
    for file_info in subfiles_info:
        folder_path = file_info['folderpath'].strip('/').split('/')  # Split folder path into parts
        parent_item = rootItem  # Start from the root
        # Iterate through each part of the folder path and create nodes if they don't exist
        for folder in folder_path:
            if folder not in folder_dict:
                folder_item = QStandardItem(folder)
                parent_item.appendRow(folder_item)
                folder_dict[folder] = folder_item
            else:
                folder_item = folder_dict[folder]
            
            # Set the parent item to the current folder for next iteration
            parent_item = folder_item
        # Add the file under the correct folder
        file_format = f"{file_info['filename']}    ({file_info['filesize']} bytes)"
        file_item = QStandardItem(file_format)
        file_item.setData({'absfilepath': file_info['absfilepath'], 
                           'fileoff': file_info['fileoff'],
                           'filesize':file_info['filesize']}, Qt.UserRole)
        parent_item.appendRow(file_item)


def open_context_menu(self, position):
    # Get the index of the selected item
    index = self.treeView.indexAt(position)
    if index.isValid():
        # Get the file path associated with the selected item
        file_path = self.model.itemFromIndex(index).data(Qt.UserRole)
        if file_path:
            self.selected_file = file_path
            # Create context menu
            context_menu = QMenu(self)
            # Add "Export" action
            export_action = context_menu.addAction("Export")
            # Connect the action to the export method
            export_action.triggered.connect(self.export_funcs[self.opened_file['meta']['extension_name']])
        
            # Add "Replace" action
            replace_action = context_menu.addAction("Replace")
            # Connect the action to the replace method
            replace_action.triggered.connect(self.replace_funcs[self.opened_file['meta']['extension_name']])
            
            # Show the context menu at the cursor position
            context_menu.exec_(self.treeView.viewport().mapToGlobal(position))
            