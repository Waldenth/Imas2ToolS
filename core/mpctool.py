# core/mpctool.py

import io
import struct
from core.readtool import *

# --- MPC 文件解析函数 ---

def load_mpc(data: bytes, mpcfileName="mpc"):
    """
    解析 MPC 文件数据，返回内部子文件信息。
    :param data: MPC 文件的完整字节数据
    :param mpcfileName: 主 MPC 文件的名称
    :return: 包含所有子文件信息的字典
    """
    f = io.BytesIO(data)
    
    # Header Reading (忽略未使用的变量，只读取需要的)
    f.seek(0x04) # 跳过 PAC
    unk = read_long(f)
    size = read_long(f)
    files = read_long(f)
    f.seek(0x30)
    infostart = read_long(f)
    msgstart = read_long(f)
    datastart = read_long(f)
    f.seek(infostart)
    
    file_info = []
    
    # 1. 读取文件信息块 (File Info)
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
    
    # 2. 读取文件名/文件夹名信息块 (String Table)
    f.seek(msgstart)
    f.seek(0x20, 1)
    
    msg = f.tell()
    names = read_short(f)
    f.seek(0x6, 1)
    names_array = read_short(f)
    names_start = read_short(f)
    
    f.seek(msg + names_array)
    
    name_sizes = []
    name_offsets = []
    
    # 读取名称大小和偏移量
    for _ in range(names):
        name_sizes.append(read_long(f))
        name_offsets.append(read_long(f))
    
    name_strings = []
    
    # 读取实际名称字符串
    for i in range(names):
        f.seek(msg + names_start + name_offsets[i])
        name_strings.append(read_string(f, name_sizes[i]))
    
    # 3. 组合信息
    mpc_file_info = []
    for i in range(files):
        filename = name_strings[file_info[i]['filenameid']]
        folderpath = name_strings[file_info[i]['filefolderid']]
        # 修正：通常根目录路径为空或'.'，这里避免 '//' 出现
        if folderpath and folderpath != '.':
            absfilepath = folderpath + '/' + filename
        else:
            absfilepath = filename

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
        "mpc_name": mpcfileName,
        "file_size": size,
        "file_nums": files,
        "infostart": infostart,
        "msgstart": msgstart,
        "datastart": datastart,
        "subfiles_info": mpc_file_info
    }
    
    return mpc_info