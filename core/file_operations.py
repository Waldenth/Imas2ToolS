# core/file_operations.py
import os
from PyQt5.QtWidgets import QFileDialog

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
        