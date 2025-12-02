from PyQt5.QtGui import  QPixmap, QImage
import struct
import dds
from PIL import Image
import numpy as np
import imageio
import io



def create_dxt5_dds(width, height, rawdata):
    # DDS 文件头的长度是 128 字节（固定格式）
    header = b'DDS ' + struct.pack('<I', 124)  # 'DDS ' + 头部大小
    header += struct.pack('<I', 0x00001007)  # flags: 高度、宽度、线性大小、像素格式
    header += struct.pack('<I', height)  # 图像高度
    header += struct.pack('<I', width)   # 图像宽度
    header += struct.pack('<I', 0)  # pitchOrLinearSize (线性大小)
    header += struct.pack('<I', 0)  # 深度 (用于 volume maps)
    header += struct.pack('<I', 0)  # mipmap count
    header += b'\x00' * 44  # reserved

    # Pixel format (32 bytes)
    header += struct.pack('<I', 32)  # 大小 76
    header += struct.pack('<I', 0x00000004)  # flags (DDPF_FOURCC)
    header += b'DXT5'  # 'DXT5' fourCC
    header += struct.pack('<I', 0)  # RGB bit count
    header += struct.pack('<I', 0)  # R bit mask
    header += struct.pack('<I', 0)  # G bit mask
    header += struct.pack('<I', 0)  # B bit mask
    header += struct.pack('<I', 0)  # A bit mask

    # Caps (16 bytes)
    header += struct.pack('<I', 0x00001000)  # caps1 (复杂图像 | 纹理)
    header += struct.pack('<I', 0)  # caps2
    header += struct.pack('<I', 0)  # caps3
    header += struct.pack('<I', 0)  # caps4
    header += struct.pack('<I', 0)  # reserved
    
    dds_data = header + rawdata
    image = Image.open(io.BytesIO(dds_data))

    return image


def create_dxt3_dds(width, height, rawdata):
    # DDS 文件头的长度是 128 字节（固定格式）
    header = b'DDS ' + struct.pack('<I', 124)  # 'DDS ' + 头部大小
    header += struct.pack('<I', 0x00001007)  # flags: 高度、宽度、线性大小、像素格式
    header += struct.pack('<I', height)  # 图像高度
    header += struct.pack('<I', width)  # 图像宽度
    header += struct.pack('<I', 0)  # pitchOrLinearSize (线性大小)
    header += struct.pack('<I', 0)  # 深度 (用于 volume maps)
    header += struct.pack('<I', 0)  # mipmap count
    header += b'\x00' * 44  # reserved
    # Pixel format (32 bytes)
    header += struct.pack('<I', 32)  # 大小
    header += struct.pack('<I', 0x00000004)  # flags (DDPF_FOURCC)
    header += b'DXT3'  # 'DXT3' fourCC
    header += struct.pack('<I', 0)  # RGB bit count
    header += struct.pack('<I', 0)  # R bit mask
    header += struct.pack('<I', 0)  # G bit mask
    header += struct.pack('<I', 0)  # B bit mask
    header += struct.pack('<I', 0)  # A bit mask
    # Caps (16 bytes)
    header += struct.pack('<I', 0x00001000)  # caps1 (复杂图像 | 纹理)
    header += struct.pack('<I', 0)  # caps2
    header += struct.pack('<I', 0)  # caps3
    header += struct.pack('<I', 0)  # caps4
    header += struct.pack('<I', 0)  # reserved
    
    dds_data = header + rawdata
    image = Image.open(io.BytesIO(dds_data))
    
    return image

def create_dxt1_dds(width, height, rawdata):
    # DDS 文件头的长度是 128 字节（固定格式）
    header = b'DDS ' + struct.pack('<I', 124)  # 'DDS ' + 头部大小
    header += struct.pack('<I', 0x00001007)  # flags: 高度、宽度、线性大小、像素格式
    header += struct.pack('<I', height)  # 图像高度
    header += struct.pack('<I', width)   # 图像宽度
    header += struct.pack('<I', 0)  # pitchOrLinearSize (线性大小)
    header += struct.pack('<I', 0)  # 深度 (用于 volume maps)
    header += struct.pack('<I', 0)  # mipmap count
    header += b'\x00' * 44  # reserved

    # Pixel format (32 bytes)
    header += struct.pack('<I', 32)  # 大小 32
    header += struct.pack('<I', 0x00000004)  # flags (DDPF_FOURCC)
    header += b'DXT1'  # 'DXT1' fourCC
    header += struct.pack('<I', 0)  # RGB bit count
    header += struct.pack('<I', 0)  # R bit mask
    header += struct.pack('<I', 0)  # G bit mask
    header += struct.pack('<I', 0)  # B bit mask
    header += struct.pack('<I', 0)  # A bit mask

    # Caps (16 bytes)
    header += struct.pack('<I', 0x00001000)  # caps1 (复杂图像 | 纹理)
    header += struct.pack('<I', 0)  # caps2
    header += struct.pack('<I', 0)  # caps3
    header += struct.pack('<I', 0)  # caps4
    header += struct.pack('<I', 0)  # reserved

    dds_data = header + rawdata
    image = Image.open(io.BytesIO(dds_data))
    
    return image


def create_raw_image(width, height, data):
    image_data = np.frombuffer(data, dtype=np.uint8)
    
    channel_num = int(image_data.size / (height*width))
    
    if channel_num == 2:
        argb_data = image_data.reshape((height, width, channel_num))
        G = argb_data[:, :, 0]
        B = argb_data[:, :, 1]
        R = np.zeros((height, width), dtype=np.uint8)
        A = np.ones((height, width), dtype=np.uint8) * 255 
        image = np.stack((R, G, B, A), axis=-1)
        image =  Image.fromarray(image, mode='RGBA')
        return image
    elif channel_num == 4:
        argb_data = image_data.reshape((height, width, 4))
        argb_data = argb_data[:, :, [1, 2, 3, 0]]
        image = Image.fromarray(argb_data, 'RGBA')
        return image
    else:
        return None