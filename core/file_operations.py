# core/file_operations.py
import os
from PyQt5.QtWidgets import QFileDialog

class FileOperations:
    """
    负责处理底层的文件导入、导出、解析等核心业务逻辑。
    """
    
    @staticmethod
    def replace_file_logic(item_meta: dict):
        """导入文件到特定路径"""
        # 在这里执行实际的文件导入代码（例如：打开文件选择框，读取新文件，更新资源）
        print(f"CORE: 开始导入新资源到目标路径: {item_meta}")
        # 示例：假设导入成功
        return True

    @staticmethod
    def export_file_logic(file_data: bytes, full_path: str, file_name: str):
        """导出文件"""

        default_save_path = os.path.join(full_path, file_name)
        
        save_path, _ = QFileDialog.getSaveFileName(
            None, "Export File", default_save_path, "All Files (*)"
        )
        
        if not save_path:
            return None
        
        target_dir = os.path.dirname(save_path) or "."
        os.makedirs(target_dir, exist_ok=True)
        
        with open(save_path, 'wb') as f:
            f.write(file_data)
        
        return save_path