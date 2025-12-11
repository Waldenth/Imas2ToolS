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
from PyQt5.QtCore import QTimer


class AppController(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.fileoperations = FileOperations()
        
        self.fileoperations.opened_file = {'type': None, 'data': None, 'name': 'untitled.bin'} # <--- 统一存储当前打开的文件数据
        
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
        self.actionImport_from_directory.triggered.connect(self.handle_import_from_directory)
        self.actionExport_all_images.triggered.connect(self.handle_export_all_images)

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
        
        
        if item_data.get('name') is not None \
            and item_type == "file_image":
            # 这是一个可预览的位图文件
            self.display_image(item_data)
        elif item_type == 'file_texture':
            # 这是一个可预览的 DDS 纹理文件
            self.display_texture(item_data)
        else:
            # 清空预览区或显示元数据
            self.preview_label.clear_image()
            self.preview_label.setText("No preview available for this item.")
        
        selected_item_name = 'N/A'
        msg = ""

        if item_data.get('type') == 'folder':
            selected_item_name = item_data.get('path', 'N/A')
            msg = f"Selected folder: {selected_item_name}"
        else:
            selected_item_name = item_data.get('path', 'N/A')
            msg = f"Selected file: {selected_item_name}"
            
        self.statusbar.showMessage(msg)


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
                self.fileoperations.opened_file = {'type': file_type, 'data': file_data, 'name': root_name}

                if file_type == 'mpc':
                    # 调用 mpctool 解析文件
                    self.mpc_file_info = load_mpc_beta(file_data, root_name)
                    loaded_info = self.mpc_file_info
                    
                elif file_type == 'tsk':
                    # TODO: TSK 文件解析逻辑
                    self.tsk_file_info = load_tsk_beta(file_data, root_name.split('.')[0])
                    loaded_info = self.tsk_file_info

                elif file_type == 'nut':
                    # TODO: NUT 文件解析逻辑
                    # 调用 nuttool 解析文件
                    self.nut_file_info = load_nut_beta(file_data, root_name)
                    loaded_info = self.nut_file_info
        
                
                if loaded_info:
                    # 关键修改：传入 file_type 和 loaded_info
                    self.update_folder_structure(root_name, file_type, loaded_info)
                    self.statusbar.showMessage(f"Successfully loaded and parsed {root_name}.")


            except Exception as e:
                self.statusbar.showMessage(f"Error loading file: {e}")
                print(f"Error loading file: {e}")
        else:
            self.statusbar.showMessage(f"Open .{file_type} canceled.")


    # --- 文件树更新方法 (更新签名和根节点设置) ---
    
    def update_folder_structure(self, root_name: str, file_type: str, info: dict):
        """
        根据解析后的树形信息 (item.json 样式)，重建 TreeWidget。
        """

        # 清空现有结构
        self.treeWidget.clear()

        root_display_name = self._format_item_name(info.get('name', root_name), info.get('size', 0))
        root_item = QTreeWidgetItem(self.treeWidget, [root_display_name])

        rootInfo = info
        rootInfo.update({
            'type': f"file_{file_type}",
            'path': info.get('name', root_name),
        })

        root_item.setData(0, Qt.UserRole, rootInfo)

        # 递归构建（修改后的 info 会被同步）
        self._build_recursive_structure(root_item, file_type, rootInfo, parent_path=info.get('name', root_name))

        # 确保最终数据同步回 rootInfo
        root_item.setData(0, Qt.UserRole, rootInfo)
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
        save_dir = os.getcwd()
        file_name = self.fileoperations.opened_file.get('name')
        default_save_path = os.path.join(save_dir, file_name)
        
        save_path, _ = QFileDialog.getSaveFileName(
            None, "Save As", default_save_path, "All Files (*)"
        )
        
        self.fileoperations.export_file_logic(
            self.fileoperations.opened_file.get('data'),
            save_path
        )
        
        self.statusbar.showMessage(f"File saved as: {save_path}")
        

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
            
            # 递归导出全部选项
            export_all_files_action = QAction("Export All Files (Recursive)", self)
            export_all_files_action.triggered.connect(lambda: self.handle_export_all_recursive(item_meta))
            menu.addAction(export_all_files_action)
            
            if item_meta.get('type') not in ['file_nut', 'file_tsk', 'file_mpc','folder']:
                export_all_action.setEnabled(False)          
                export_all_files_action.setEnabled(False)
                
            if item_meta.get('type') in ['folder']:
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
        
        if item_meta.get('size', 0) != len(replace_file):
            QMessageBox.warning(None, "Error", "The size of the replacement file does not match the original file.")
            return
        
        success = self.fileoperations.replace_file_logic(item_meta, replace_file)
        if success:
            self.statusbar.showMessage(f"Replace successful for: {item_meta.get('name')}")
            if need_refresh:
                self.display_texture(item_meta) # 重新显示替换后的图像

             
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

        offset = item_meta.get('offset')
        size = item_meta.get('size')
        file_name = item_meta.get('name')
        
        
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
                file_data = dds_to_png(file_data, texFmt, width, height)
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
        """异步处理 Export All 菜单点击事件，并转发给核心逻辑"""

        if item_meta is None:
            self.statusbar.showMessage("No item metadata available for Export All.")
            return

        if item_meta.get('subItem') is None:
            self.statusbar.showMessage("No subfiles available for Export All.")
            return

        subfiles_info = item_meta.get('subItem', [])
        default_dir = os.path.join(os.getcwd(), item_meta.get('name', '') + '_folder')
        dir_path = QFileDialog.getExistingDirectory(
            None,
            "Export Directory",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not dir_path:
            return

        export_file_info ={
            "parent_file": item_meta.get('path').split('/')[0],
            "file_list": []
        }

        self._export_queue = list(subfiles_info)
        self._export_dir = dir_path
        self._export_count = 0
        self._export_file_info = export_file_info
        self._export_json_path = os.path.join(dir_path, "{}.json".format(item_meta.get('name')))

        def process_next():
            if not self._export_queue:
                FileOperations.save_json_to_file(self._export_file_info, self._export_json_path)
                self.statusbar.showMessage(f"Export All completed to directory: {self._export_dir}, total {self._export_count} files.")
                return
            subfile = self._export_queue.pop(0)
            offset = subfile.get('offset')
            size = subfile.get('size')
            file_name = subfile.get('name')
            if size == 0:
                QTimer.singleShot(10, process_next)
                return
            file_data = self.fileoperations.opened_file["data"][offset:offset+size]
            # 记录导出信息, png/dds均以原始名称记录
            self._export_file_info["file_list"].append({
                "name": file_name,
                "offset": offset,
                "size": size,
            })
            
            if file_name.endswith(".dds"):
                file_name = file_name[:-4] + ".png"
                height = subfile.get('height')
                width = subfile.get('width')
                texFmt = subfile.get('texFmt')
                try:
                    file_data = dds_to_png(file_data, texFmt, width, height)
                except Exception as e:
                    QMessageBox.warning(None, "Error", f"Failed to convert DDS to image: {str(e)}")
                    QTimer.singleShot(10, process_next)
                    return
            save_path = os.path.join(self._export_dir, file_name)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            FileOperations.export_file_logic(file_data, save_path)
            self._export_count += 1
            self.statusbar.showMessage(f"Exported: {file_name}, {self._export_count}/{len(subfiles_info)}")
            QTimer.singleShot(10, process_next)

        process_next()
    
    
    def handle_export_all_recursive(self, item_meta: dict):
        """异步处理 Export All Recursive 菜单点击事件，每个文件导出时更新 statusbar"""

        if item_meta is None:
            self.statusbar.showMessage("No item metadata available for Export All Recursive.")
            return

        if item_meta.get('subItem') is None:
            self.statusbar.showMessage("No subfiles available for Export All Recursive.")
            return

        default_dir = os.path.join(os.getcwd(), item_meta.get('name', '')+'_recursive')
        dir_path = QFileDialog.getExistingDirectory(
            None,
            "Export Directory",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not dir_path:
            return

        export_file_info ={
            "parent_file": item_meta.get('path').split('/')[0],
            "file_list": []
        }
        
        self._export_file_info = export_file_info
        self._export_json_path = os.path.join(dir_path, "{}.json".format(item_meta.get('name')))
        self._export_count = 0
        self._export_total = 0
        
        # 先计算总文件数
        def count_files(subitems):
            count = 0
            for subitem in subitems:
                ctype = subitem.get('type', 'file')
                size = subitem.get('size', 0)
                
                if ctype == 'folder':
                    count += count_files(subitem.get('subItem', []))
                elif ctype not in ['file_mpc', 'file_tsk', 'file_nut'] and size > 0:
                    count += 1
                elif ctype in ['file_mpc', 'file_tsk', 'file_nut']:
                    count += count_files(subitem.get('subItem', []))
            return count
        
        self._export_total = count_files(item_meta.get('subItem', []))
        
        # 创建文件队列
        def build_queue(subitems, current_dir, queue):
            for subitem in subitems:
                name = subitem.get('name')
                size = subitem.get('size', 0)
                offset = subitem.get('offset', 0)
                ctype = subitem.get('type', 'file')
                target_path = os.path.join(current_dir, name)

                if ctype == 'folder':
                    os.makedirs(target_path, exist_ok=True)
                    build_queue(subitem.get('subItem', []), target_path, queue)
                elif ctype in ['file_mpc', 'file_tsk', 'file_nut']:
                    os.makedirs(target_path, exist_ok=True)
                    build_queue(subitem.get('subItem', []), target_path, queue)
                else:
                    if size > 0:
                        queue.append({
                            'name': name,
                            'size': size,
                            'offset': offset,
                            'height': subitem.get('height'),
                            'width': subitem.get('width'),
                            'texFmt': subitem.get('texFmt'),
                            'target_path': target_path
                        })
        
        export_queue = []
        build_queue(item_meta.get('subItem', []), dir_path, export_queue)
        
        def process_next():
            if not export_queue:
                FileOperations.save_json_to_file(self._export_file_info, self._export_json_path)
                self.statusbar.showMessage(f"Export All Recursive completed to directory: {dir_path}, total {self._export_count} files.")
                return
            
            file_item = export_queue.pop(0)
            name = file_item['name']
            size = file_item['size']
            offset = file_item['offset']
            target_path = file_item['target_path']
            
            try:
                file_data = self.fileoperations.opened_file["data"][offset:offset+size]
                
                png_name = name
                
                if name.endswith(".dds"):
                    png_name = name[:-4] + ".png"
                    height = file_item['height']
                    width = file_item['width']
                    texFmt = file_item['texFmt']
                    try:
                        file_data = dds_to_png(file_data, texFmt, width, height)
                        target_path = target_path[:-4] + ".png"
                    except Exception as e:
                        QMessageBox.warning(None, "Error", f"Failed to convert DDS to image: {str(e)}")
                        self._export_count += 1
                        self.statusbar.showMessage(f"Failed: {png_name}, {self._export_count}/{self._export_total}")
                        QTimer.singleShot(10, process_next)
                        return
                
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                FileOperations.export_file_logic(file_data, target_path)
                relative_path = os.path.relpath(target_path, dir_path)
                
                # 原文件为dds,导出为png, 但是记录为dds
                if name.endswith(".dds"):
                    relative_path = relative_path[:-4] + ".dds"
                
                # 记录导出信息, png/dds均以原始名称记录
                self._export_file_info["file_list"].append({
                    "name": name,
                    "path": relative_path,
                    "offset": offset,
                    "size": size,
                })
                self._export_count += 1
                self.statusbar.showMessage(f"Exported: {name}, {self._export_count}/{self._export_total}")
            except Exception as e:
                self._export_count += 1
                self.statusbar.showMessage(f"Error exporting {name}: {str(e)}")
            
            QTimer.singleShot(10, process_next)
        
        process_next()

    
    def handle_import_from_directory(self):
        """处理 Tools > Import from directory 点击事件"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select a directory to import files from",
            ""
        )
        
        if not directory:
            return
        
        try:
            self.statusbar.showMessage(f"Importing files from {directory}...")
            # 这里可以添加具体的导入逻辑
            # 例如扫描目录中的文件，导入到当前打开的数据结构中
            QMessageBox.information(self, "Import", f"Successfully imported files from:\n{directory}")
            self.statusbar.showMessage("Import completed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import: {str(e)}")
            self.statusbar.showMessage("Import failed.")

    def handle_export_all_images(self):
        """处理 Tools > Export all images 点击事件"""
        if not self.fileoperations.opened_file.get('data'):
            QMessageBox.warning(self, "Warning", "No file is currently open.")
            return
        
        item_meta = self.treeWidget.topLevelItem(0).data(0, Qt.UserRole)
        
        if item_meta is None:
            self.statusbar.showMessage("Please open a file first.")
            return
        
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select a directory to export images to",
            ""
        )
        
        if not directory:
            return
        
        export_file_info ={
            "parent_file": item_meta.get('path').split('/')[0],
            "file_list": []
        }
        
        
        self._export_file_info = export_file_info
        # 注意导出图片的export_json_path包含_images后缀
        self._export_json_path = os.path.join(directory, "{}_images.json".format(item_meta.get('name')))
        self._export_count = 0
        self._export_total = 0
        self._export_dir = directory
        
        
        def count_images(subitems):
            count = 0
            for subitem in subitems:
                ctype = subitem.get('type', 'file')
                size = subitem.get('size', 0)
                
                if ctype == 'folder':
                    count += count_images(subitem.get('subItem', []))
                elif ctype == 'file_image' and size > 0:
                    count += 1
                elif ctype == 'file_texture' and size > 0:
                    count += 1
                elif ctype in ['file_mpc', 'file_tsk', 'file_nut']:
                    count += count_images(subitem.get('subItem', []))
            return count
        
        self._export_total = count_images(item_meta.get('subItem', []))
        
        
        def build_image_queue(subitems, current_dir, queue):
            for subitem in subitems:
                name = subitem.get('name')
                size = subitem.get('size', 0)
                offset = subitem.get('offset', 0)
                ctype = subitem.get('type', 'file')

                if ctype == 'folder':
                    build_image_queue(subitem.get('subItem', []), current_dir, queue)
                elif ctype == 'file_image' and size > 0:
                    queue.append({
                        'name': name,
                        'size': size,
                        'offset': offset,
                    })
                elif ctype == 'file_texture' and size > 0:
                    queue.append({
                        'name': name,
                        'size': size,
                        'offset': offset,
                        'height': subitem.get('height'),
                        'width': subitem.get('width'),
                        'texFmt': subitem.get('texFmt'),
                    })
                elif ctype in ['file_mpc', 'file_tsk', 'file_nut']:
                    build_image_queue(subitem.get('subItem', []), current_dir, queue)
                else:
                    continue
        
        image_queue = []
        build_image_queue(item_meta.get('subItem', []), directory, image_queue)
        
        def process_next():
            if not image_queue:
                FileOperations.save_json_to_file(self._export_file_info, self._export_json_path)
                self.statusbar.showMessage(f"Export all images completed to directory: {directory}, total {self._export_count} images.")
                return 
            file_item = image_queue.pop(0)
            name = file_item['name']
            size = file_item['size']
            offset = file_item['offset']
            
            try:
                if size == 0:
                    self._export_count += 1
                    QTimer.singleShot(10, process_next)
                    return
                file_data = self.fileoperations.opened_file["data"][offset:offset+size]
                
                # 记录导出信息, png/dds均以原始名称记录
                self._export_file_info["file_list"].append({
                    "name": name,
                    "offset": offset,
                    "size": size,
                })
                
                if name.endswith(".dds"):
                    new_name = name[:-4] + ".png"
                    height = file_item.get('height')
                    width = file_item.get('width')
                    texFmt = file_item.get('texFmt')
                    try:
                        file_data = dds_to_png(file_data, texFmt, width, height)
                        name = new_name
                    except Exception as e:
                        QMessageBox.warning(None, "Error", f"Failed to convert DDS to image: {str(e)}")
                        self._export_count += 1
                        self.statusbar.showMessage(f"Failed: {name}, {self._export_count}/{self._export_total}")
                        QTimer.singleShot(10, process_next)
                        return
                save_path = os.path.join(self._export_dir, name)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                FileOperations.export_file_logic(file_data, save_path)
                self._export_count += 1
                self.statusbar.showMessage(f"Exported image: {name}, {self._export_count}/{self._export_total}")
            except Exception as e:
                self._export_count += 1
                self.statusbar.showMessage(f"Error exporting image {name}: {str(e)}")
                
            QTimer.singleShot(10, process_next)
            
        process_next()
       
                   
    
    
    def display_texture(self, image_meta):
        offset = image_meta["offset"]
        size = image_meta["size"]
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
            
    def display_image(self, image_meta):

        offset = image_meta["offset"]
        size = image_meta ["size"]
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
    

    def _build_recursive_structure(self, parent_item: QTreeWidgetItem, file_type: str, node: dict, parent_path: str):
        """
        根据 item.json 样式的节点递归构建树。node 包含 name/type/size/offset/subItem。
        直接修改 node['subItem'][i] 中的数据，保证父节点数据同步更新。
        """

        subitem_list = node.get('subItem', [])
        for idx, child in enumerate(subitem_list):
            name = child.get('name', '')
            size = child.get('size', 0)
            offset = child.get('offset', 0)
            ctype = child.get('type', 'file')

            display_name = self._format_item_name(name, size)
            full_path = f"{parent_path}/{name}" if parent_path else name

            item = QTreeWidgetItem(parent_item, [display_name])
            
            # 直接修改原始 child 引用，确保同步回 node['subItem'][idx]
            child.update({
                'path': full_path,
            })
            
            if size == 0:
                item.setForeground(0, Qt.gray)  # 设置为灰色字体表示空文件
                continue
            
            # 若是文件夹则递归
            if ctype == 'folder':
                self._build_recursive_structure(item, file_type, child, full_path)
                
            elif ctype == 'file_tsk':
                sub_items = load_tsk_beta(
                    self.fileoperations.opened_file['data'][offset:offset+size],
                    name.split('.')[0],
                    baseOffset=offset
                )
                # 确保 subItem 列表存在
                if 'subItem' not in child:
                    child['subItem'] = []
                # 直接修改 child 字典中的 subItem
                child['subItem'].clear()
                child['subItem'].extend(sub_items.get('subItem', []))
                
                self._build_recursive_structure(item, ctype, child, full_path)
                
            elif ctype == 'file_nut':
                sub_items = load_nut_beta(
                    self.fileoperations.opened_file['data'][offset:offset+size],
                    name,
                    baseOffset=offset
                )
                # 确保 subItem 列表存在
                if 'subItem' not in child:
                    child['subItem'] = []
                # 直接修改 child 字典中的 subItem
                child['subItem'].clear()
                child['subItem'].extend(sub_items.get('subItem', []))
                
                self._build_recursive_structure(item, ctype, child, full_path)
                
            elif ctype == 'file_mpc':
                sub_items = load_mpc_beta(
                    self.fileoperations.opened_file['data'][offset:offset+size],
                    name,
                    baseOffset=offset
                )
                # 确保 subItem 列表存在
                if 'subItem' not in child:
                    child['subItem'] = []
                # 直接修改 child 字典中的 subItem
                child['subItem'].clear()
                child['subItem'].extend(sub_items.get('subItem', []))
                
                self._build_recursive_structure(item, ctype, child, full_path)
                
            else:
                ext = name.split('.')[-1].lower() if '.' in name else ''
                if child.get('subItem'):
                    # 已经是树结构，直接递归
                    self._build_recursive_structure(item, ext or ctype, child, full_path)
            
            item.setData(0, Qt.UserRole, child)