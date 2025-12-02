import io
import struct
from core.readtool import *

def load_nut(data, nutfileName="nut"):
    f = io.BytesIO(data)
    magic = f.read(4).decode('ascii')
    if magic != "NTP3":
        raise Exception("Invalid NUT file")
    version = read_short(f)
    texCount = read_short(f)
    f.seek(0x10, 0) # ABS
    
    nut_file_info = []
    for i in range(0,texCount):
        offset = f.tell()
        chunkSize = read_long(f)
        unk = read_long(f)
        textSize = read_long(f)
        headerSize = read_short(f)
        '''
            0：从文件的开头开始计算（默认值）。
            1：从文件的当前位置开始计算。
            2：从文件的末尾开始计算。
        '''
        f.seek(0x4, 1)
        texType = read_short(f)
        width = read_short(f)
        height = read_short(f)
        f.seek(0x8,1)
        texOffset = read_long(f)
        f.seek(offset+headerSize-0x08, 0)
        texID = read_long(f)
        f.seek(0x4, 1)
        if version == 0x200:
            f.seek(offset+texOffset, 0)
        texDataOffset = f.tell()
        texData = f.read(textSize)
        texFmt = ""
        
        if texType == 0:
            texFmt = "DXT1"
        elif texType == 1:
            texFmt = "DXT3"
        elif texType == 2:
            texFmt = "DXT5"
        else:
            texFmt = "RAW"
        
        fileName = "{0}_{1}x{2}_{3}.dds".format(texID, width, height, texFmt)

        nut_file_info.append({
            'filename': fileName,
            'folderpath': nutfileName,
            'absfilepath': nutfileName+"/"+fileName,
            'fileoff': texDataOffset,
            'filesize':textSize,
            'width': width,
            'height': height,
            'texFmt': texFmt
        })

        if version == 0x200:
            f.seek(offset+headerSize, 0)
        else:
            f.seek(offset+chunkSize, 0)
    nut_info ={
        "file_size": len(data),
        "file_nums": texCount,
        "subfiles_info": nut_file_info
    }
    return nut_info