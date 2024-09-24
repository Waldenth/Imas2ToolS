import os
import json
from tools import *
import io
from PyQt5.QtWidgets import  QFileDialog, QMessageBox
import operations

def load_mpc(data):
    f = io.BytesIO(data)
    pac = read_long(f)
    unk = read_long(f)
    size = read_long(f)
    files = read_long(f)
    f.seek(0x30)
    infostart = read_long(f)
    msgstart = read_long(f)
    datastart = read_long(f)
    f.seek(infostart)
    
    file_info = []
    
    # Read file info
    for _ in range(files):
        f.seek(0x8, 1)  # Skip 8 bytes
        filesize = read_long(f)
        fileoffset = read_long(f)
        filenameid = read_long(f)
        filefolderid = read_long(f)
        f.seek(0x8, 1)  # Skip another 8 bytes
        
        file_info.append({
            'filesize': filesize,
            'fileoffset': fileoffset,
            'filenameid': filenameid,
            'filefolderid': filefolderid
        })
    
    f.seek(msgstart)
    
    f.seek(0x20, 1)  # Skip 0x20 bytes
    
    msg = f.tell()
    names = read_short(f)
    f.seek(0x6, 1)  # Skip 6 bytes
    names_array = read_short(f)
    names_start = read_short(f)
    
    f.seek(msg + names_array)
    
    name_sizes = []
    name_offsets = []
    
    # Read name sizes and offsets
    for _ in range(names):
        name_sizes.append(read_long(f))
        name_offsets.append(read_long(f))
    
    name_strings = []
    
    # Read actual names
    for i in range(names):
        f.seek(msg + names_start + name_offsets[i])
        name_strings.append(read_string(f, name_sizes[i]))
    
    mpc_file_info = []
    for i in range(files):
        filename = name_strings[file_info[i]['filenameid']]
        folderpath = name_strings[file_info[i]['filefolderid']]
        absfilepath = folderpath + '/' + filename
        fileoff = file_info[i]['fileoffset'] + datastart
        filesize = file_info[i]['filesize']
        mpc_file_info.append({
            'filename': filename,
            'folderpath': folderpath,
            'absfilepath': absfilepath,
            'fileoff': fileoff,
            'filesize': filesize,
            'filenameid': file_info[i]['filenameid'],
            'filefolderid': file_info[i]['filefolderid']
        })
        
    
    mpc_info= {
        "file_size":size,
        "file_nums":files,
        "infostart":infostart,
        "msgstart":msgstart,
        "datastart":datastart,
        "subfiles_info":mpc_file_info
    }
    
    return mpc_info

def export_file(self):
    if self.selected_file:
        # Open a file dialog to save the file
        save_path, _ = QFileDialog.getSaveFileName(self, 'Save File', self.selected_file['absfilepath'].split('/')[-1], 'All Files (*)')
        if save_path:
            # Simulate file export by copying the selected file (in real case, you'd copy or generate the file)
            file_data = read_offset_data(self.opened_file["data"], self.selected_file['fileoff'], self.selected_file['filesize'])
            try:
                with open(save_path, 'wb') as f_out:
                    f_out.write(file_data)
                # Show success message
                QMessageBox.information(self, "Exported", f"File exported successfully\n{save_path}")
            except FileNotFoundError:
                # Show error message
                QMessageBox.warning(self, "Export Failed", "The selected file does not exist.")
                
def replace_file(self):
    if self.selected_file:
        file_path, _ = QFileDialog.getOpenFileName(self, 'Open file', '', 'All Files (*)')
        if file_path:
            # Load the file to be replaced
            with open(file_path, 'rb') as f:
                new_file_data = f.read()    
            
            new_file_size = len(new_file_data)
            old_file_abspath = self.selected_file['absfilepath']
            old_file_offset = self.selected_file['fileoff']
            old_file_size = self.selected_file['filesize']
            
            file_idx = 0
            while(self.opened_file["meta"]["subfiles_info"][file_idx]['absfilepath'] != old_file_abspath):
                file_idx += 1
            
                        
            old_padding = (16 - old_file_size % 16) % 16
            new_padding = (16 - new_file_size % 16) % 16
            
            delta_size = (new_file_size+new_padding) - (old_file_size+old_padding)
            delta_padding = new_padding - old_padding
            
            f = io.BytesIO(self.opened_file["data"])
            
            new_mpc_data = bytearray()
            
            if delta_size !=0:
                
                infostart = self.opened_file["meta"]["infostart"]
                msgstart = self.opened_file["meta"]["msgstart"]
                datastart = self.opened_file["meta"]["datastart"]

                new_mpc_data.extend(f.read(old_file_offset))
                new_mpc_data.extend(new_file_data)
                if delta_padding > 0:
                    for _ in range(delta_padding):
                        new_mpc_data.extend(b'\00')
                    f.seek(old_file_offset + old_file_size)
                else:
                    skip_padding = abs(delta_padding)
                    f.seek(old_file_offset + old_file_size + skip_padding)
                new_mpc_data.extend(f.read())
                
                
                # Update the file size in the mpc file info
                offset = self.opened_file["meta"]["infostart"] + 0x20 * file_idx
                new_mpc_data[offset+8:offset+12] = \
                    (new_file_size).to_bytes(4, 'big')
                
                for i in range(file_idx+1, self.opened_file["meta"]["file_nums"]):
                    offset = infostart + 0x20 * i
                    new_mpc_data[offset+12:offset+16] = \
                        (self.opened_file["meta"]["subfiles_info"][i]["fileoff"] + delta_size - datastart).to_bytes(4, 'big')
                
                mpc_file_total_size = self.opened_file["meta"]["file_size"] - old_file_size + new_file_size
                new_mpc_data[8:12] = mpc_file_total_size.to_bytes(4, 'big')
                
            else:
                new_mpc_data.extend(f.read(old_file_offset))
                new_mpc_data.extend(new_file_data)
                f.seek(old_file_offset + old_file_size)
                new_mpc_data.extend(f.read())       

            self.opened_file["data"] = new_mpc_data
            self.opened_file["meta"].update(load_mpc(self.opened_file["data"]))
            operations.fresh_tree_view(self)
            QMessageBox.information(self, "Replaced", f"File replaced successfully\n{old_file_abspath} \nhas been replaced by\n{file_path}")