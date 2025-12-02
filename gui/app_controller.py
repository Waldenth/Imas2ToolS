# gui/app_controller.py

import os
from PyQt5.QtWidgets import QMainWindow, QMenu, QAction, QTreeWidgetItem,\
    QFileDialog
from PyQt5 import uic
from PyQt5.QtCore import Qt, QPoint
from core.file_operations import FileOperations # 导入核心逻辑
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QEvent

from gui.scalable_label import ScalableLabel # 导入自定义控件
from core.mpctool import *
from core.nuttool import *
from core.imagetool import *

class AppController(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.opened_file = {'type': None, 'data': None} # <--- 统一存储当前打开的文件数据
        
        self.mpc_file_info = None # <-- 新增：存储解析后的 MPC 文件信息
        
        self.nut_file_info = None # <-- 新增：存储解析后的 NUT 文件信息

        self.load_ui()
        self.init_logic()


    def load_ui(self):
        """加载 mainwindow.ui 界面文件"""
        ui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mainwindow.ui")
        if os.path.exists(ui_path):
            uic.loadUi(ui_path, self)
        else:
            raise FileNotFoundError(f"UI 文件未找到: {ui_path}")
        
    def init_logic(self):
        # 构造图标文件的相对路径
        icon_file_name = "app_icon.png" 
        
        # 假设 gui/app_controller.py 在 gui/ 目录下
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(project_root, "resources", icon_file_name)
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"警告: 图标文件未找到，请检查路径: {icon_path}")

        # --- 2. 替换 QLabel 为 ScalableLabel 并修复样式丢失问题 ---
        
        # **关键修复步骤 A:** 捕获 Designer 中设置的原始样式和文本
        original_stylesheet = self.preview_label.styleSheet()
        original_text = self.preview_label.text()
        
        # 找到 Designer 中创建的 QLabel 的父布局
        parent_layout = self.preview_label.parentWidget().layout()
        
        # 移除旧的 QLabel 控件
        self.preview_label.setParent(None)
        
        # 实例化自定义的 ScalableLabel
        self.preview_label = ScalableLabel(self.scrollAreaWidgetContents)
        self.preview_label.setObjectName("preview_label") 
        
        # **关键修复步骤 B:** 应用捕获的样式和文本到新的 ScalableLabel
        self.preview_label.setStyleSheet(original_stylesheet)
        self.preview_label.setText(original_text)

        # 将新控件添加到布局中
        parent_layout.addWidget(self.preview_label)

        # --- 3. 初始设置 ---
        self.treeWidget.clear()
        self.statusbar.showMessage("Ready.")
        
        # **关键修改:** 设置 QSplitter 的拉伸因子 (保持左侧小，右侧大)
        # 0 代表 treeWidget，1 代表 scrollArea (预览窗口)
        # treeWidget 占 1 份，预览窗口占 5 份。
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 8)
        
        # --- 4. 信号连接 ---
        
        # 连接 QTreeWidget 的点击信号
        self.treeWidget.itemClicked.connect(self.handle_tree_item_click)
        
        # 连接主菜单 Action
        self.actionOpen_mpc.triggered.connect(lambda: self.handle_open_file("mpc"))
        self.actionOpen_tsk.triggered.connect(lambda: self.handle_open_file("tsk"))
        self.actionOpen_nut.triggered.connect(lambda: self.handle_open_file("nut"))
        
        self.actionConvert.triggered.connect(self.handle_convert)
        self.actionSave_as.triggered.connect(self.handle_save_as)

        # 设置文件树的右键菜单
        self.treeWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(self.show_context_menu)

        # self (AppController) 监控 self.scrollArea 上的事件
        self.scrollArea.installEventFilter(self)

        # 给 TreeWidget 添加一个测试节点
        # root = QTreeWidgetItem(self.treeWidget, ["root_folder"])
        # child = QTreeWidgetItem(root, ["data.bin"])
        # root.setExpanded(True)


    # --- 新增点击处理方法 ---
    def handle_tree_item_click(self, item: QTreeWidgetItem, column: int):
        """处理文件树节点点击事件"""
        # 从节点获取用户数据
        item_data = item.data(0, Qt.UserRole)
        
        if not item_data:
            return

        item_type = item_data.get('type')
        
        if item_type == 'texture':
            # 这是一个可预览的 DDS 纹理文件
            self.display_image(item_data)
        elif item_type in ('mpc_root', 'nut_root', 'folder'):
            # 清空预览区或显示元数据
            self.preview_label.setText(f"Selected: {item_data.get('filename') or item_data.get('path')}")


    def handle_open_file(self, file_type: str):
        """
        弹出文件选择框，并根据 file_type 过滤文件类型
        """
        
        # 定义文件过滤器字典
        filters = {
            "mpc": "MPC Files (*.mpc)",
            "tsk": "TSK Files (*.tsk)",
            "nut": "NUT Files (*.nut)"
        }
        
        # 获取对应的过滤器，如果类型不在字典中则显示所有文件
        file_filter = filters.get(file_type, "All Files (*)")
        
        # 弹出文件选择框
        file_name, selected_filter = QFileDialog.getOpenFileName(
            self, 
            f"Open .{file_type} File",      # 窗口标题
            "",                             # 初始目录 (空字符串表示使用默认或上次目录)
            file_filter                     # 文件过滤器
        )
        
        if file_name:
            self.statusbar.showMessage(f"Loading {file_name}...")
            try:
                with open(file_name, 'rb') as f:
                    file_data = f.read()
                
                root_name = os.path.basename(file_name)
                loaded_info = None

                # 关键：清空旧数据并存储新数据
                self.opened_file['data'] = file_data
                self.opened_file['type'] = file_type

                if file_type == 'mpc':
                    # 调用 mpctool 解析文件
                    self.mpc_file_info = load_mpc(file_data, root_name)
                    loaded_info = self.mpc_file_info
                    
                elif file_type == 'tsk':
                    # TODO: TSK 文件解析逻辑
                    self.statusbar.showMessage(f"File {root_name} loaded. TSK parser not implemented yet.")
                    return # 暂不更新树状图

                elif file_type == 'nut':
                    # TODO: NUT 文件解析逻辑
                    # 调用 nuttool 解析文件
                    self.nut_file_info = load_nut(file_data, root_name)
                    loaded_info = self.nut_file_info
        
                
                if loaded_info:
                    # 关键修改：传入 file_type 和 loaded_info
                    self.update_folder_structure(root_name, file_type, loaded_info)
                    self.statusbar.showMessage(f"Successfully loaded and parsed {root_name}. ({loaded_info.get('file_nums', 0)} files found)")


            except Exception as e:
                self.statusbar.showMessage(f"Error loading file: {e}")
                print(f"Error loading file: {e}")
        else:
            self.statusbar.showMessage(f"Open .{file_type} canceled.")


    # --- 文件树更新方法 (更新签名和根节点设置) ---
    def update_folder_structure(self, root_name: str, file_type: str, info: dict):
        """
        根据解析后的信息，清空并重建 Folder Structure TreeWidget。
        
        :param root_name: 根节点名称 (文件名)
        :param file_type: 文件类型 ('mpc', 'tsk', 'nut')
        :param info: 解析后的数据字典
        """
        # 清空现有结构
        self.treeWidget.clear()
        
        # 存储文件夹结构，键为路径，值为 QTreeWidgetItem
        folder_map = {}
        
        # 创建根节点 (主文件本身)
        root_item = QTreeWidgetItem(self.treeWidget, [root_name])
        
        # >>> 关键修改在这里: 根据传入的 file_type 动态设置根节点类型 <<<
        root_item.setData(0, Qt.UserRole, {
            'type': f'{file_type}_root',  # 例如: mpc_root, tsk_root
            'path': root_name,
            'info': info  # 存储完整信息
        })
        # -------------------------------------------------------------
        
        folder_map['.'] = root_item # 根目录映射

        # --- 根据文件类型执行子结构构建 ---
        
        if file_type == 'mpc':
            # MPC 文件的子结构构建逻辑
            
            # 遍历所有子文件信息
            for subfile in info.get('subfiles_info', []):
                path_parts = subfile['absfilepath'].split('/')
                current_path = []
                
                # 1. 创建或获取父文件夹节点 (此段逻辑不变)
                for i in range(len(path_parts) - 1):
                    part = path_parts[i]
                    if part and part != '.':
                        current_path.append(part)
                    
                    parent_key = '/'.join(current_path[:-1]) if current_path[:-1] else '.'
                    current_key = '/'.join(current_path)
                    
                    if current_key not in folder_map:
                        parent_item = folder_map.get(parent_key, root_item)
                        folder_item = QTreeWidgetItem(parent_item, [part])
                        folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'path': current_key})
                        folder_map[current_key] = folder_item
                        
                # 2. 添加文件节点
                parent_key = subfile.get('folderpath', '') if subfile.get('folderpath') else '.'
                parent_item = folder_map.get(parent_key, root_item)
                
                file_item = QTreeWidgetItem(parent_item, [subfile['filename']])
                
                subfile['type'] = 'file'
                file_item.setData(0, Qt.UserRole, subfile)
                
                filename = subfile['filename']
                if filename.lower().endswith('.nut'):
                    file_item.setExpanded(True)
                    if subfile['filesize'] > 0:
                        nutFileData = self.opened_file['data'][subfile['fileoff']:subfile['fileoff']+subfile['filesize']]
                        nut_info = load_nut(nutFileData, filename)
                        # 递归构建 NUT 子结构
                        for sub_dds_file in nut_info.get('subfiles_info', []):
                            nut_file_item = QTreeWidgetItem(file_item, [sub_dds_file['filename']])
                            sub_dds_file["fileoff"] += subfile['fileoff']  # 修正偏移量
                            sub_dds_file['type'] = 'texture' # 类型设置为 'texture' 或 'file'
                            nut_file_item.setData(0, Qt.UserRole, sub_dds_file)
                    
                    

        elif file_type == 'tsk':
            # TODO: 实现 TSK 文件的子结构构建逻辑
            pass

        elif file_type == 'nut':
            # NUT 文件没有子文件夹，所有子文件直接挂在根节点下
            for subfile in info.get('subfiles_info', []):
                file_item = QTreeWidgetItem(root_item, [subfile['filename']])
                
                # 将完整的子文件信息附加到节点上
                subfile['type'] = 'texture' # 类型设置为 'texture' 或 'file'
                file_item.setData(0, Qt.UserRole, subfile)
            pass


        # 展开根节点
        root_item.setExpanded(True)



    def handle_convert(self):
        """处理主菜单 Convert 点击事件"""
        self.statusbar.showMessage("Handling Convert...")
        # 检查是否勾选了 Use Dict
        if self.cb_use_dict.isChecked():
            print("Convert: Use Dict enabled.")
        # ... 调用 FileOperations ...
    
    def handle_save_as(self):
        """处理主菜单 Save As 点击事件"""
        self.statusbar.showMessage("Handling Save As...")
        # ... 调用 FileOperations ...  


    # --- 右键菜单相关方法 ---
    def show_context_menu(self, point: QPoint):
        """在 treeWidget 的指定位置 point 显示右键菜单"""
        # 获取被点击的树形控件项 (QTreeWidgetItem)
        item = self.treeWidget.itemAt(point)
        
        # 只有点击到具体的项目时才显示菜单
        if item:
            # 获取被点击项目的完整路径（这里简单地使用文本作为路径）
            item_path = item.text(0)
            
            menu = QMenu(self)
            
            # 导入选项
            import_action = QAction("Import...", self)
            # 使用 lambda 匿名函数将当前项目的路径作为参数传递给 handler
            import_action.triggered.connect(lambda: self.handle_import(item_path))
            menu.addAction(import_action)
            
            # 导出选项
            export_action = QAction("Export...", self)
            export_action.triggered.connect(lambda: self.handle_export(item_path))
            menu.addAction(export_action)
            
            # 在鼠标的全局位置显示菜单
            menu.exec_(self.treeWidget.mapToGlobal(point))
        else:
            # 如果点击在空白区域，可以显示一个不同的菜单，或者不显示
            pass
            
    def handle_import(self, path: str):
        """处理 Import 菜单点击事件，并转发给核心逻辑"""
        self.statusbar.showMessage(f"Attempting to Import for: {path}")
        if FileOperations.import_file_logic(path):
            self.statusbar.showMessage(f"Import successful for: {path}")
        else:
             self.statusbar.showMessage(f"Import failed for: {path}")
             
    def handle_export(self, path: str):
        """处理 Export 菜单点击事件，并转发给核心逻辑"""
        self.statusbar.showMessage(f"Attempting to Export for: {path}")
        if FileOperations.export_file_logic(path):
            self.statusbar.showMessage(f"Export successful for: {path}")
        else:
             self.statusbar.showMessage(f"Export failed for: {path}")
             
             
    def display_image(self, image_meta):
        offset = image_meta["fileoff"]
        size = image_meta["filesize"]
        width = image_meta['width']
        height = image_meta['height']
        texFmt = image_meta['texFmt']
        
        file_data = self.opened_file["data"][offset:offset+size]
        image = None
        try:
            if texFmt == "DXT1":
                image = create_dxt1_dds(width, height, file_data)
            elif texFmt == "DXT3":
                image = create_dxt3_dds(width, height, file_data)
            elif texFmt == "DXT5":
                image = create_dxt5_dds(width, height, file_data)
            else:
                image = create_raw_image(width, height, file_data)
        except Exception as e:
            self.preview_label.setText(f"Failed to load image: {str(e)}")
            return
                
        qimage  = QImage(image.tobytes(), width, height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimage)
        
        
        if not pixmap.isNull():
            #scaled_pixmap = pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.set_image(pixmap)
        else:
            self.preview_label.setText("Failed to load image. pixmap is null.")