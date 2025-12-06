# gui/app_controller.py

import os
from PyQt5.QtWidgets import QMainWindow, QMenu, QAction, QTreeWidgetItem,\
    QFileDialog, QMessageBox
from PyQt5 import uic
from PyQt5.QtCore import Qt, QPoint
from core.file_operations import FileOperations # 导入核心逻辑
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QEvent

from gui.scalable_label import ScalableLabel # 导入自定义控件
from core.mpctool import *
from core.nuttool import *
from core.imagetool import *
from core.tsktool import *
from io import BytesIO


class AppController(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.fileoperations = FileOperations()
        
        self.fileoperations.opened_file = {'type': None, 'data': None} # <--- 统一存储当前打开的文件数据
        
        #self.opened_file = {'type': None, 'data': None} # <--- 统一存储当前打开的文件数据
        
        self.mpc_file_info = None # <-- 新增：存储解析后的 MPC 文件信息
        
        self.nut_file_info = None # <-- 新增：存储解析后的 NUT 文件信息
        
        self.tsk_file_info = None # <-- 新增：存储解析后的 TSK 文件信息

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
        
        
        if item_data.get('filename') is not None \
            and (item_data.get('filename').lower().endswith('.png') or item_data.get('filename').lower().endswith('.jpg')):
            # 这是一个可预览的位图文件
            self.display_bitmap(item_data)
        elif item_type == 'dds':
            # 这是一个可预览的 DDS 纹理文件
            self.display_image(item_data)
        elif item_type in ('mpc_root', 'nut_root','folder', 'file'):
            # 清空预览区或显示元数据
            self.preview_label.clear_image()
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
        
        # 基础过滤器
        base_filter = filters.get(file_type, "")

        # 拼接全部文件过滤器
        if base_filter:
            file_filter = f"{base_filter};;All Files (*)"
        else:
            file_filter = "All Files (*)"
        
        
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
                self.fileoperations.opened_file = {'type': file_type, 'data': file_data}
                self.fileoperations.opened_file['type'] = file_type

                if file_type == 'mpc':
                    # 调用 mpctool 解析文件
                    self.mpc_file_info = load_mpc(file_data, root_name)
                    loaded_info = self.mpc_file_info
                    
                elif file_type == 'tsk':
                    # TODO: TSK 文件解析逻辑
                    self.tsk_file_info = load_tsk(file_data, root_name.split('.')[0])
                    loaded_info = self.tsk_file_info

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
        根据解析后的信息，清空并重建 Folder Structure TreeWidget (使用递归)。
        """

        # 清空现有结构
        self.treeWidget.clear()
        
        # 1. 创建根节点 (主文件本身)
        root_filesize = info.get('file_size', 0)
        root_display_name = self._format_item_name(root_name, root_filesize)
        root_item = QTreeWidgetItem(self.treeWidget, [root_display_name])
        
        root_item.setData(0, Qt.UserRole, {
            'type': f'{file_type}_root',
            'path': root_name,
            'info': info
        })
        
        # 2. 调用递归方法构建子结构
        # 初始偏移量为 0，因为它是主文件
        self._build_recursive_structure(root_item, file_type, info, 0) 
        
        # 3. 展开根节点
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
            item_meta = item.data(0, Qt.UserRole) or {}
            
            menu = QMenu(self)
            
            # 导入选项
            import_action = QAction("Replace", self)
            # 使用 lambda 匿名函数将当前项目的路径作为参数传递给 handler
            import_action.triggered.connect(lambda: self.handle_replace(item_meta))
            menu.addAction(import_action)
            
            # 导出选项
            export_action = QAction("Export", self)
            export_action.triggered.connect(lambda: self.handle_export(item_meta))
            menu.addAction(export_action)

            # 导出全部选项
            export_all_action = QAction("Export All", self)
            export_all_action.triggered.connect(lambda: self.handle_export_all(item_meta))
            menu.addAction(export_all_action)
            
            if item_meta.get('type') not in ['nut', 'tsk', 'mpc_root', 'nut_root', 'tsk_root']:
                export_all_action.setEnabled(False)          
            if item_meta.get('type') in ['nut_root', 'tsk_root', 'mpc_root', 'folder']:
                import_action.setEnabled(False)
                export_action.setEnabled(False)
                
                
            
            # 在鼠标的全局位置显示菜单
            menu.exec_(self.treeWidget.mapToGlobal(point))
        else:
            # 如果点击在空白区域，可以显示一个不同的菜单，或者不显示
            pass
            
    def handle_replace(self, item_meta: dict):
        """处理 Replace 菜单点击事件，并转发给核心逻辑"""
        if item_meta is None:
            self.statusBar.showMessage("No item metadata available for Replace.")
            return
        
        replaced_file_path, _ = QFileDialog.getOpenFileName(
            None, "Select File to Replace", "", "All Files (*)"
        )
        
        if not replaced_file_path:
            return None
        
        replace_file = open(replaced_file_path, 'rb').read()
        need_refresh = False
        if replaced_file_path.endswith(".dds"):
            need_refresh = True
            replace_file = replace_file[128:]  # 去掉 DDS 头部，保留原始纹理数据
        
        if item_meta.get('filesize', 0) != len(replace_file):
            QMessageBox.warning(None, "Error", "The size of the replacement file does not match the original file.")
            return
        
        success = self.fileoperations.replace_file_logic(item_meta, replace_file)
        if success:
            self.statusbar.showMessage(f"Replace successful for: {item_meta.get('filename')}")
            if need_refresh:
                self.display_image(item_meta) # 重新显示替换后的图像

             
    def handle_export(self, item_meta: dict):
        """处理 Export 菜单点击事件，并转发给核心逻辑"""
        if item_meta is None:
            self.statusBar.showMessage("No item metadata available for Export.")
            return
        
        # 通过右键菜单传来的 item 需要存储，或从树中重新获取
        # 这里我们在 show_context_menu 中也传递 item 本身
        '''
        item = self.treeWidget.itemAt(self.treeWidget.mapFromGlobal(self.cursor().pos()))
        if not item:
            self.statusbar.showMessage("Cannot determine item context.")
            return
        '''
        if item_meta.get('type') == 'folder':
            self.statusbar.showMessage("Cannot export a folder. Please select a file.")
            return

        offset = item_meta.get('fileoff')
        size = item_meta.get('filesize')
        file_name = item_meta.get('filename')
        
        
        if size == 0:
            QMessageBox.information(None, "Info", "The selected file is empty. Nothing to export.")
            return 
        
        file_data = self.fileoperations.opened_file["data"][offset:offset+size]
        
        if file_name.endswith(".dds"):
            file_name = file_name[:-4] + ".png"
            height = item_meta.get('height')
            width = item_meta.get('width')
            texFmt = item_meta.get('texFmt')
            
            try:
                if texFmt == "DXT1":
                    image = create_dxt1_dds(width, height, file_data)
                elif texFmt == "DXT3":
                    image = create_dxt3_dds(width, height, file_data)
                elif texFmt == "DXT5":
                    image = create_dxt5_dds(width, height, file_data)
                else:
                    image = create_raw_image(width, height, file_data)
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                file_data = buffer.getvalue()
            except Exception as e:
                QMessageBox.warning(None, "Error", f"Failed to convert DDS to image: {str(e)}")
        
        # 使用完整路径的目录部分作为默认保存目录
        save_dir = os.getcwd()
        
        default_save_path = os.path.join(save_dir, file_name)
        
        save_path, _ = QFileDialog.getSaveFileName(
            None, "Export File", default_save_path, "All Files (*)"
        )
        
        if not save_path:
            return None
        
        target_dir = os.path.dirname(save_path) or "."
        os.makedirs(target_dir, exist_ok=True)
                
        FileOperations.export_file_logic(file_data, save_path)
       
        self.statusbar.showMessage(f"Export successful for: {save_path}")

             
    def handle_export_all(self, item_meta: dict):
        """处理 Export All 菜单点击事件，并转发给核心逻辑"""
        if item_meta is None:
            self.statusbar.showMessage("No item metadata available for Export All.")
            return
        
        info = item_meta.get('info')
        
        if info is None or info.get('subfiles_info') is None:
            self.statusbar.showMessage("No subfiles available for Export All.")
            return
        
        subfiles_info = info.get('subfiles_info')
        
        default_dir = os.path.join(os.getcwd(), item_meta.get('filename', 'exported_dir'))
        
        dir_path = QFileDialog.getExistingDirectory(
            None,
            "Export Directory",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not dir_path:
            return
        
        baseOffset = item_meta.get('fileoff') or 0
        
        for subfile in subfiles_info:
            offset = subfile.get('fileoff') + baseOffset
            size = subfile.get('filesize')
            file_name = subfile.get('filename')
            
            if size == 0:
                continue  # 跳过空文件
            file_data = self.fileoperations.opened_file["data"][offset:offset+size]
            
            if file_name.endswith(".dds"):
                file_name = file_name[:-4] + ".png"
                height = subfile.get('height')
                width = subfile.get('width')
                texFmt = subfile.get('texFmt')
                
                try:
                    if texFmt == "DXT1":
                        image = create_dxt1_dds(width, height, file_data)
                    elif texFmt == "DXT3":
                        image = create_dxt3_dds(width, height, file_data)
                    elif texFmt == "DXT5":
                        image = create_dxt5_dds(width, height, file_data)
                    else:
                        image = create_raw_image(width, height, file_data)
                    buffer = BytesIO()
                    image.save(buffer, format="PNG")
                    file_data = buffer.getvalue()
                except Exception as e:
                    QMessageBox.warning(None, "Error", f"Failed to convert DDS to image: {str(e)}")
                    return
            
            save_path = os.path.join(dir_path, file_name)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            FileOperations.export_file_logic(file_data, save_path)
        
        self.statusbar.showMessage(f"Export All completed to directory: {dir_path}, total {len(subfiles_info)} files.")
            
            
            
    
    
        
    def display_image(self, image_meta):
        offset = image_meta["fileoff"]
        size = image_meta["filesize"]
        width = image_meta['width']
        height = image_meta['height']
        texFmt = image_meta['texFmt']
        
        file_data = self.fileoperations.opened_file["data"][offset:offset+size]
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
            
    def display_bitmap(self, image_meta):

        offset = image_meta["fileoff"]
        size = image_meta ["filesize"]
        image_data = self.fileoperations.opened_file["data"][offset:offset+size]
        image = None
        
        try:
            image = Image.open(io.BytesIO(image_data))
            width, height = image.size
        except Exception as e:
            self.preview_label.setText(f"Failed to load image: {str(e)}")
            return
        mode = image.mode
        if mode == 'RGB':
            image = image.convert('RGBA')
        qimage  = QImage(image.tobytes(), width, height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimage)
        
        if not pixmap.isNull():
            #scaled_pixmap = pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.set_image(pixmap)
        else:
            self.preview_label.setText("Failed to load image. pixmap is null.")
            
            
    # 辅助方法：格式化文件名和大小
    def _format_item_name(self, filename: str, filesize: int) -> str:
        """格式化显示名称，包含字节数"""
        return f"{filename} ({filesize} bytes)"
    

    def _build_recursive_structure(self, parent_item: QTreeWidgetItem, file_type: str, info: dict, parent_offset: int):
        """
        递归构建文件结构，处理嵌套的容器文件 (如 NUT, TSK, MPC)。

        :param parent_item: 当前子文件要挂载到的父级 QTreeWidgetItem。
        :param file_type: 当前容器的类型 ('mpc', 'tsk', 'nut')。
        :param info: 当前容器的解析数据 (包含 'subfiles_info')。
        :param parent_offset: 父容器在原始大文件中的起始偏移量。
        """
        
        # 存储文件夹结构，键为路径，值为 QTreeWidgetItem (仅用于 MPC/TSK 的文件夹结构)
        folder_map = {'.': parent_item}
        
        # --- 递归遍历子文件 ---
        for subfile in info.get('subfiles_info', []):
            subfile_filename = subfile['filename']
            
            # 0. 修正文件偏移量 (所有子文件的偏移量都基于它们的容器文件)
            # 将相对偏移量修正为相对于原始大文件的绝对偏移量
            subfile['fileoff'] += parent_offset 

            # 1. 提取文件信息
            subfile_filesize = subfile.get('filesize', 0)
            display_name = self._format_item_name(subfile_filename, subfile_filesize)
            subfile_extension = subfile_filename.split('.')[-1].lower()
            
            # 2. TSK 和 MPC 需要路径/文件夹结构，NUT 不需要
            if file_type == 'mpc' or file_type == 'tsk':
                
                # --- 2a. 路径/文件夹结构创建 ---
                path_parts = subfile['absfilepath'].split('/')
                current_path = []
                
                # 遍历路径，创建文件夹节点
                current_parent = parent_item
                for i in range(len(path_parts) - 1):
                    part = path_parts[i]
                    if part and part != '.':
                        current_path.append(part)
                    
                    parent_key = '/'.join(current_path[:-1]) if current_path[:-1] else '.'
                    current_key = '/'.join(current_path)
                    
                    if current_key not in folder_map:
                        parent_folder_item = folder_map.get(parent_key, current_parent) # 根级容器或上级文件夹
                        folder_item = QTreeWidgetItem(parent_folder_item, [part])
                        folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'path': current_key})
                        folder_map[current_key] = folder_item
                        
                        # 检查是否为 NUT 容器在路径中，并自动展开 (仅在 path_parts 中)
                        if part.lower().endswith('.nut') or part.lower().endswith('.tsk'):
                            folder_item.setExpanded(True) # 容器在路径中时展开
                    
                    current_parent = folder_map.get(current_key, current_parent)
                
                # 2b. 设置文件节点的父级
                parent_item_for_file = folder_map.get(subfile.get('folderpath', '') if subfile.get('folderpath') else '.', parent_item)
            
            else: # NUT 文件，直接挂载到 parent_item 下
                parent_item_for_file = parent_item

            is_container = subfile_extension in ['nut', 'tsk']
            container_path_key = subfile.get('absfilepath', '')
            
            if is_container and container_path_key in folder_map:
                # 如果是容器文件，并且它已经在路径解析中被创建成了文件夹节点（即 folder_map 中存在），
                # 则使用该现有节点作为递归的父节点，避免创建重复的 file_item。
                file_item = folder_map[container_path_key]
                # 我们仍然需要更新它的数据，特别是修正后的 fileoff
                file_item.setData(0, Qt.UserRole, subfile)
            else:
                # 否则，创建一个新的文件节点（常规文件或不在路径中被解析的 NUT 文件）
                file_item = QTreeWidgetItem(parent_item_for_file, [display_name])
                subfile['type'] = subfile_extension if subfile_extension in ['nut', 'tsk', 'dds'] else 'file'
                file_item.setData(0, Qt.UserRole, subfile)
            


            # 4. 检查是否为容器文件，如果是，则进行递归解析
            if is_container :
                if subfile['filesize'] == 0:
                    continue           # 跳过空文件
                
                # 读取子文件数据
                try:
                    # 假设 self.fileoperations.opened_file['data'] 存储了整个原始文件数据
                    # 如果这个方法是在 AppController 中调用的，那么这个数据应该可以访问
                    file_data = self.fileoperations.opened_file['data'][subfile['fileoff']:subfile['fileoff'] + subfile['filesize']]
                except Exception as e:
                    print(f"读取内嵌文件 {subfile_filename} 数据失败: {e}")
                    continue # 跳过无法读取的文件
                    
                # 解析子文件
                if subfile_extension == 'nut':
                    sub_info = load_nut(file_data, subfile_filename.split('.')[0])
                elif subfile_extension == 'tsk':
                    sub_info = load_tsk(file_data, subfile_filename.split('.')[0])
                
                # 递归调用自身，将子文件的内容挂载到当前 file_item 下
                if sub_info:
                    #subfile['subfiles_info'] = sub_info
                    data = file_item.data(0, Qt.UserRole)
                    data.update({
                        'info': {
                            'file_nums': sub_info.get('file_nums', 0),
                            'subfiles_info': sub_info.get('subfiles_info', [])
                        }
                    })
                    file_item.setData(0, Qt.UserRole, data)
                    
                    # 注意：这里需要确保文件项在递归前已经设置了子节点，才能成功展开
                    self._build_recursive_structure(file_item, subfile_extension, sub_info, subfile['fileoff'])
                    # 在添加完子结构后，设置展开状态
                    file_item.setExpanded(True)
                    