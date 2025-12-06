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
        '''
        argb_data = image_data.reshape((height, width, channel_num))
        G = argb_data[:, :, 0]
        B = argb_data[:, :, 1]
        R = np.zeros((height, width), dtype=np.uint8)
        A = np.ones((height, width), dtype=np.uint8) * 255 
        image = np.stack((R, G, B, A), axis=-1)
        image =  Image.fromarray(image, mode='RGBA')
        return image
        '''
        rgba_data = a1r5g5b5_to_rgba8888_conversion(data, width, height)
        image = Image.fromarray(rgba_data, mode='RGBA')
        return image
    
    elif channel_num == 4:
        rgba_data = image_data.reshape((height, width, 4))
        rgba_data = rgba_data[:, :, [1, 2, 3, 0]]
        image = Image.fromarray(rgba_data, 'RGBA')
        return image
    else:
        return None
    
def a1r5g5b5_to_rgba8888_conversion(rgb565_bytes, width, height, is_big_endian=True):
    """
    将 A1R5G5B5 格式的原始字节数据转换为 RGBA8888 numpy 数组
    """
    # 1. 确定字节序并读取数据
    dtype_str = '>u2' if is_big_endian else '<u2'
        
    try:
        # 读取 16 位无符号整数数据
        data_16bit = np.frombuffer(rgb565_bytes, dtype=np.dtype(dtype_str))
    except ValueError as e:
        print(f"字节长度错误！期望: {width * height * 2} 字节, 实际: {len(rgb565_bytes)} 字节")
        raise e
    
    # 2. 提取 A1、R5、G5、B5 分量
    
    # R5 (14-10位)
    R5 = (data_16bit >> 10) & 0x1F  
    # G5 (9-5位)
    G5 = (data_16bit >> 5) & 0x1F   
    # B5 (4-0位)
    B5 = data_16bit & 0x1F           
    # A1 (15位)
    A1 = (data_16bit >> 15) & 0x01   # 得到 0 或 1

    # 3. 扩展到 8 位 (R, G, B, A)

    # R5 -> R8 扩展: (R5 << 3) ^ (R5 >> 2)
    R8 = (R5 << 3) ^ (R5 >> 2) 
    # G5 -> G8 扩展: (G5 << 3) ^ (G5 >> 2)
    G8 = (G5 << 3) ^ (G5 >> 2) 
    # B5 -> B8 扩展: (B5 << 3) ^ (B5 >> 2)
    B8 = (B5 << 3) ^ (B5 >> 2) 
    
    # A1 -> A8 扩展: A0 = (x >> 15) * 255。即 0 变 0，1 变 255
    A8 = A1 * 255
    
    # 4. 合并 R, G, B, A 分量
    # Pillow 期望的格式是 (R, G, B, A)
    rgba8888_array = np.stack([R8, G8, B8, A8], axis=-1).astype(np.uint8)
    
    # 5. 重塑为图像的 (height, width, 4) 形状
    return rgba8888_array.reshape((height, width, 4))

