# core/file_operations.py
import os
from PyQt5.QtWidgets import QFileDialog
from PIL import Image
import numpy as np
from core.imagetool import *


class FileOperations:
    """
    负责处理底层的文件导入、导出、解析等核心业务逻辑。
    """
    
    opened_file = {'type': None, 'data': None, 'name': 'untitled.bin'}   # 存储当前打开的文件数据
    
    
    def replace_file_logic(self, item_meta: dict, new_file_data: bytes):
        """导入文件到特定路径"""
        # 在这里执行实际的文件导入代码（例如：打开文件选择框，读取新文件，更新资源）
        #print(f"CORE: 开始导入新资源到目标路径: {item_meta}")
        offset = item_meta['offset']
        size = item_meta['size']
        
        new_opened_file_data = bytearray(self.opened_file['data'])
        new_opened_file_data[offset:offset+size] = new_file_data
        
        self.opened_file['data'] = bytes(new_opened_file_data)
        # 示例：假设导入成功
        return True
    
    def replace_texture_logic(self, texture_file_path, item_meta: dict):
        """导入纹理文件到特定路径"""
        if '_RAW.dds' in texture_file_path:
            # RAW DDS 纹理导入逻辑
            image = Image.open(texture_file_path)
            height = image.height
            width = image.width
            rgba_data = np.asarray(image, dtype=np.uint8)
            
            item_size = item_meta['size']
            
            if item_size == rgba_data.size:
                # RGBA8888 格式
                # Convert RGBA to ARGB
                argb_dds_data = rgba_data[:, :, [3, 0, 1, 2]].tobytes ()
                if len(argb_dds_data) != item_meta['size']:
                    raise ValueError("Imported texture size does not match the original size.\
                        Expected: {}, Actual: {}".format(item_meta['size'], len(argb_dds_data)))
                self.replace_file_logic(item_meta, argb_dds_data)
            elif item_size * 2 == rgba_data.size:
                # A1R5G5B5 格式
                argb_dds_data = rgba8888_to_a1r5g5b5_conversion(rgba_data, width, height)
                if len(argb_dds_data) != item_meta['size']:
                    raise ValueError("Imported texture size does not match the original size.\
                        Expected: {}, Actual: {}".format(item_meta['size'], len(argb_dds_data)))
                self.replace_file_logic(item_meta, argb_dds_data)
            else:
                raise ValueError("Unsupported image channel number for RAW DDS import: ".format(texture_file_path))
            
            return
        with open(texture_file_path, 'rb') as f:
            f.read(128) # 跳过 DDS 头部
            new_dds_data = f.read()
            if len(new_dds_data) != item_meta['size']:
                raise ValueError("Imported texture size does not match the original size.\
                    Expected: {}, Actual: {}".format(item_meta['size'], len(new_dds_data)))
            self.replace_file_logic(item_meta, new_dds_data)
        
        

    @staticmethod
    def export_file_logic(file_data: bytes, export_path: str):
        """导出文件"""
        with open(export_path, 'wb') as f:
            f.write(file_data)
    
    @staticmethod
    def get_file_type(filename: str):
        """根据文件扩展名判断文件类型"""
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.mpc']:
            return 'file_mpc'
        elif ext in ['.tsk']:
            return 'file_tsk'
        elif ext in ['.nut']:
            return 'file_nut'
        elif ext in ['.dds']:
            return 'file_texture'
        elif ext in ['.jpg', '.png']:
            return 'file_image'
        elif ext in ['.xmb']:
            return 'file_xmb'
        else:
            return 'file_unknown'
    
    @staticmethod
    def save_json_to_file(json_data: dict, export_path: str):
        """将 JSON 数据保存到文件"""
        import json
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
            
    @staticmethod
    def load_json_from_file(import_path: str):
        """从文件加载 JSON 数据"""
        import json
        with open(import_path, 'r', encoding='utf-8') as f:
            return json.load(f)