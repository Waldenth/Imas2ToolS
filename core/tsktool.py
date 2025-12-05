# core/tsktool.py

import io
import struct
import pathlib
from core.readtool import *


def load_tsk(data, tskfileName="tsk"):
    file = io.BytesIO(data)
    file.seek(0)
    TSK = read_long(file)
    FILES = read_long(file)
    FILESIZE = []
    FILEOFFSET = []
    for _ in range(FILES):
        FILESIZE.append(read_long(file))
        FILEOFFSET.append(read_long(file))
    XMBSTART = FILEOFFSET[0]
    file.seek(XMBSTART)
    file.seek(0x4, 1)
    INFO = read_long(file)
    file.seek(0x10, 1)
    INFOOFFSET = read_long(file)
    INFOLIST = read_long(file)
    file.seek(0x4, 1)
    COMMANDOFFSET = read_long(file)
    NAMEOFFSET = read_long(file)
    x = 0
    BASE = tskfileName
    BASE += ".xmb"
    NAMES = [BASE]
    x += 1
    file.seek(XMBSTART)
    file.seek(INFOOFFSET, 1)
    for i in range(INFO):
        file.seek(0x4, 1)
        INFOCOUNT = read_short(file)
        file.seek(0xA, 1)
        TMP1 = file.tell()
        if i == 0:
            file.seek(XMBSTART)
            file.seek(INFOLIST, 1)
            TMP2 = file.tell()
        else:
            file.seek(TMP2)
        for _ in range(INFOCOUNT):
            COMMANDSTART = read_long(file)
            NAMESTART = read_long(file)
            TMP2 = file.tell()
            file.seek(XMBSTART)
            file.seek(COMMANDOFFSET + COMMANDSTART, 1)
            COMMAND = read_varstring(file)
            file.seek(XMBSTART)
            file.seek(NAMEOFFSET + NAMESTART, 1)
            SNAME = read_varstring(file)
            if COMMAND == "path":
                SPATH = SNAME
            elif COMMAND == "name":
                FNAME = SNAME
            elif COMMAND == "index":
                if SPATH == ".":
                    NAMES.append(FNAME)
                else:
                    SPATH += FNAME
                    NAMES.append(SPATH)
            file.seek(TMP2)
        file.seek(TMP1)
    x = 0
    
    tsk_file_info = []
    for i in range(FILES):
        NAME2 = tskfileName
        NAME2 += "/"
        NAME2 += NAMES[x]
        x += 1
        file.seek(FILEOFFSET[i])
        HEADER = read_long(file)
        if HEADER == 0x7a6c6962:
            SIZE = read_long(file)
            ZSIZE = read_long(file)
            FILEOFF = file.tell()
            cur_file_folder = str(pathlib.Path(NAME2).parent)
            cur_file_name = pathlib.Path(NAME2).name
            
            tsk_file_info.append({
                "filename": cur_file_name,
                "folderpath": cur_file_folder,
                "absfilepath": NAME2,
                "fileoff": FILEOFF,
                "filesize": ZSIZE
            })
            
            
        else:
            cur_file_folder = str(pathlib.Path(NAME2).parent)
            cur_file_name = pathlib.Path(NAME2).name
            tsk_file_info.append({
                "filename": cur_file_name,
                "folderpath": cur_file_folder,
                "absfilepath": NAME2,
                "fileoff": FILEOFFSET[i],
                "filesize": FILESIZE[i]
            })
    tsk_info ={
        "file_size": len(data),
        "file_nums": FILES,
        "subfiles_info": tsk_file_info
    }
    return tsk_info