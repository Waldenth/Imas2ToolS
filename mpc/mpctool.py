import os
import json
from tools import *
import io

def load_mpc(file_path):
    with open(file_path, 'rb') as f:
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
        binData = None
        with open(file_path, 'rb') as f:
            binData = f.read()