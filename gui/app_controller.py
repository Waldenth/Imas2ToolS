# gui/app_controller.py

import os
import traceback
import json
import subprocess
from PyQt5.QtWidgets import QMainWindow, QMenu, QAction, QTreeWidgetItem,\
    QFileDialog, QMessageBox,QApplication
from PyQt5 import uic
from PyQt5.QtCore import Qt, QPoint
from core.file_operations import FileOperations # 导入核心逻辑
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QEvent
from PyQt5.QtGui import QBrush
from PIL import Image, ImageDraw
from gui.scalable_label import ScalableLabel # 导入自定义控件
from core.mpctool import *
from core.nuttool import *
from core.imagetool import *
from core.tsktool import *
from core.xmbtool import *
from io import BytesIO
from PyQt5.QtCore import QTimer
from core.scb_file_formats import scb
from core.scb_file_formats import msg
from core.scb_file_formats import scb0
from core.scbtool import *
from core.workers.task_worker import TaskRunner
from core.services.dds_converter import convert_png_to_dds_task
from core.services.font_builder import build_font_task
from core.services.char_map_builder import remap_chars_task
from core.services.nfh_parser import parse_nfh_task, modify_nfh_item

class AppController(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.fileoperations = FileOperations()
        
        self.fileoperations.opened_file = {'type': None, 'data': None, 'name': 'untitled.bin'} # <--- 统一存储当前打开的文件数据
        
        self.mpc_file_info = None # <-- 新增：存储解析后的 MPC 文件信息
        
        self.nut_file_info = None # <-- 新增：存储解析后的 NUT 文件信息
        
        self.tsk_file_info = None # <-- 新增：存储解析后的 TSK 文件信息
        
        self.charMap = { 'import': {}, 'export': {} }  # 存储字符映射表
        
        self.runner = None  # 用于存储 TaskRunner 实例，避免被垃圾回收
        
        self.tree_mode = "folder"  # 当前树形结构模式，默认为 "folder"
        
        self.glyphs = {} # render font 的时候存储字形数据，key 是字符，value 是字形数据字典
        
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
        
        import_char_txt = "import.txt"
        export_char_txt = "export.txt"
        
        # 假设 gui/app_controller.py 在 gui/ 目录下
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(project_root, "resources", icon_file_name)
        import_char_path = os.path.join(project_root, "resources", import_char_txt)
        export_char_path = os.path.join(project_root, "resources", export_char_txt)
        nvdxt_path = os.path.join(project_root, "resources", "nvdxt.exe")
        original_nfh_path = os.path.join(project_root, "resources", "im2_font.nfh")
        original_nfh_json_path = os.path.join(project_root, "resources", "im2_font.json")
        original_font_image_path = os.path.join(project_root, "resources", "im2_font.png")
        font_ttf_path = os.path.join(project_root, "resources", "DreamHanSans-W16.ttc")
        zh2jp_kanji_map_path = os.path.join(project_root, "resources", "zh2jp_kanji_map.txt")
        
        self.resources_path = os.path.join(project_root, "resources")
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"警告: 图标文件未找到，请检查路径: {icon_path}")

        if os.path.exists(import_char_path):
            self.charMap['import'] = FileOperations.load_char_map_from_file(import_char_path)

        if os.path.exists(export_char_path):
            self.charMap['export'] = FileOperations.load_char_map_from_file(export_char_path)

        # --- 2. 替换 QLabel 为 ScalableLabel 并修复样式丢失问题 ---
        
        # **关键修复步骤 A:** 捕获 Designer 中设置的原始样式和文本
        original_stylesheet = self.preview_label.styleSheet()
        original_text = self.preview_label.text()
        
        # 找到 Designer 中创建的 QLabel 的父布局
        parent_layout = self.preview_label.parentWidget().layout()
        
        # 移除旧的 QLabel 控件
        self.preview_label.setParent(None)
        
        # 字体搜索渲染容器 边距设置为 0，与cb_use_dict对齐
        self.nfh_tools_layout.setContentsMargins(0, 0, 0, 0)
        self.nfh_tools_widget.setVisible(False)
        
        
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
        
        # 连接 itemChanged 信号以处理字体属性编辑
        self.treeWidget.itemChanged.connect(self.on_item_changed)
        
        # 连接字体工具的按钮
        self.nfh_char_search_button.clicked.connect(self.search_char_in_tree)
        self.nfh_char_render_button.clicked.connect(self.render_font_preview)  # TODO: 传入选中字符的数据
        
        # 连接主菜单 Action
        self.actionOpen_mpc.triggered.connect(lambda: self.handle_open_file(file_type = "mpc"))
        self.actionOpen_tsk.triggered.connect(lambda: self.handle_open_file(file_type = "tsk"))
        self.actionOpen_nut.triggered.connect(lambda: self.handle_open_file(file_type = "nut"))
        self.actionOpen_font.triggered.connect(lambda: self.handle_open_font())
        
        self.actionCreateSCB.triggered.connect(self.handle_convert_scb)
        self.actionExtractSCB.triggered.connect(self.handle_extract_scb)
        
        self.actionBuildCharMap.triggered.connect(
            lambda: self.handle_build_char_map(zh2jp_kanji_map_path, original_nfh_json_path))
        self.actionBuildFontImageNFH.triggered.connect(
            lambda: self.handle_build_font_image_nfh(original_nfh_path, original_nfh_json_path, original_font_image_path, font_ttf_path))
        
        self.actionGenerateNFHJson.triggered.connect(self.handle_generate_nfh_json)
        
        self.actionConvertDDSDXT1.triggered.connect(
            lambda: self.handle_convert_dds("DXT1A", nvdxt_path))
        self.actionConvertDDSDXT3.triggered.connect(
            lambda: self.handle_convert_dds("DXT3", nvdxt_path))
        self.actionConvertDDSDXT5.triggered.connect(
            lambda: self.handle_convert_dds("DXT5", nvdxt_path))
        self.actionRewriteXMB.triggered.connect(self.handle_rewrite_xmb_file)
        self.actionSave_as.triggered.connect(self.handle_save_as)
        self.actionImport_from_directory.triggered.connect(self.handle_import_from_directory)
        self.actionExport_all_images.triggered.connect(self.handle_export_all_images)
        self.actionExport_all_xmbs.triggered.connect(self.handle_export_all_xmbs)

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
        if getattr(self, "tree_mode", None) != "folder":
            return
        
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


    def handle_open_file(self, file_type: str, file_path: str = None):
        # 打开文件时隐藏字体工具窗口
        self.nfh_tools_widget.setVisible(False)
        # QApplication.processEvents()
        
        """
        弹出文件选择框，并根据 file_type 过滤文件类型
        """
        if file_path is None:
            # 定义文件过滤器字典
            filters = {
                "mpc": "MPC Files (*.mpc)",
                "tsk": "TSK/S2D/MOT Files (*.tsk *.s2d *.mot)",
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
        else:
            file_name = file_path
        
        if file_name:
            self.statusbar.showMessage(f"Loading {file_name}...")
            try:
                with open(file_name, 'rb') as f:
                    file_data = f.read()
                
                root_name = os.path.basename(file_name)
                # s2d 也作为 tsk 处理, 但需要区分
                if root_name.endswith('.s2d'):
                    file_type = 's2d'
                if root_name.endswith('.mot'):
                    file_type = 'mot'
                
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

                elif file_type == 's2d':
                    self.tsk_file_info = load_tsk_beta(file_data, root_name.split('.')[0])
                    self.tsk_file_info['name'] = root_name.split('.')[0] + '.s2d'
                    loaded_info = self.tsk_file_info
                elif file_type == 'mot':
                    self.tsk_file_info = load_tsk_beta(file_data, root_name.split('.')[0])
                    self.tsk_file_info['name'] = root_name.split('.')[0] + '.mot'
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
                traceback.print_exc()
        else:
            self.statusbar.showMessage(f"Open .{file_type} canceled.")


    # --- 文件树更新方法 (更新签名和根节点设置) ---
    
    def update_folder_structure(self, root_name: str, file_type: str, info: dict):
        """
        根据解析后的树形信息 (item.json 样式)，重建 TreeWidget。
        """
        self.tree_mode = "folder"
        self.treeWidget.blockSignals(True)
        # 清空现有结构
        self.treeWidget.clear()
        self.treeWidget.setColumnCount(1)
        self.treeWidget.setHeaderLabels(["File Structure"])

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
        
        self.treeWidget.blockSignals(False)
        
    def handle_open_font(self):
        if not self.cb_use_dict.isChecked():
            reply = QMessageBox.question(None, "Warning", "You don't have Use Dict enabled.\nThe font char will not be mapped, and the rendering may be incorrect.\nContinue?", QMessageBox.Ok | QMessageBox.Cancel)
            if reply != QMessageBox.Ok:
                return
        # QApplication.processEvents()
        font_folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Font Resource Directory",
            ""
        )
        if font_folder_path:
            nfh_file_path = os.path.join(font_folder_path, "im2_font.nfh")
            font_image_path = os.path.join(font_folder_path, "im2_font.png")
            if not os.path.exists(nfh_file_path) or not os.path.exists(font_image_path):
                QMessageBox.warning(None, "Error", \
                    f"Font resource files not found in the selected directory.\nPlease ensure im2_font.nfh and im2_font.png are present in {font_folder_path}.")
                return
            self.font_image = Image.open(font_image_path)
            self.nfh_file_data = bytearray(open(nfh_file_path, 'rb').read())
            try:
                self.nfh_json = parse_nfh_task(
                    lambda msg: (
                        self.statusbar.showMessage(msg),
                        QApplication.processEvents()
                    ),
                    self.nfh_file_data
                )
            except Exception as e:
                QMessageBox.warning(None, "Error", f"Error parsing NFH file: {e}")
                return
            self.nfh_tools_widget.setVisible(True)
            self.fileoperations.opened_file = {'type': "nfh_font", 'data': self.nfh_file_data, 'name': "im2_font.nfh"}
            self.update_font_structure(self.nfh_json)
            
            self.statusbar.showMessage(
                "Font NFH loaded successfully from {}. Map:{}".format(
                    font_folder_path,
                    "Enabled" if self.cb_use_dict.isChecked() else "Disabled"
                )
            )
            try:
                self.font_render_background_image = Image.open(os.path.join(self.resources_path, "ComBackground.png"))
                self.display_image(image_meta={}, image=self.font_render_background_image)
            except Exception as e:
                QMessageBox.warning(None, "Error", f"Failed to load font background image: {e}")
    
    def update_font_structure(self, nfh_json: list):
        self.tree_mode = "font"
        self.treeWidget.blockSignals(True)
        # 清空现有结构
        self.treeWidget.clear()
        self.treeWidget.setColumnCount(2)
        self.treeWidget.setHeaderLabels(["属性", "值"])
        for idx, item in enumerate(self.nfh_json):
            char = item.get("char", "")
            # 过滤掉不可见字符
            if ord(char) < ord(' '):
                continue
            if self.cb_use_dict.isChecked() and char in self.charMap['export']:
                char = self.charMap['export'][char]
            # 顶层节点
            top_item = QTreeWidgetItem(self.treeWidget)
            top_item.setText(0, f"{char}")
            # 存 index
            top_item.setData(0, Qt.UserRole, idx)
            for key, value in item.items():
                
                self.glyphs[char] = item # 存储字形数据，key 是字符，value 是字形数据字典
                
                if key in ("char", "blockOffset"):
                    continue
                child = QTreeWidgetItem(top_item)
                child.setText(0, key)
                child.setText(1, str(value))
                # 存 key
                child.setData(0, Qt.UserRole, key)
                is_editable = key.startswith("offset") or key == "advancex"
                # 可编辑字段
                if is_editable:
                    child.setFlags(child.flags() | Qt.ItemIsEditable)
                else:
                    brush = QBrush(Qt.gray)
                    child.setForeground(0, brush)
                    child.setForeground(1, brush)
        # self.treeWidget.expandAll()
        self.treeWidget.blockSignals(False)
    
    def search_char_in_tree(self):
        text = self.nfh_char_search_bar.text()
        if not text:
            return
        target_char = text[0]  # 只取第一个字符
        # 遍历顶层节点
        for i in range(self.treeWidget.topLevelItemCount()):
            item = self.treeWidget.topLevelItem(i)
            if item.text(0) == target_char:
                # 定位到该节点
                self.treeWidget.setCurrentItem(item)
                self.treeWidget.scrollToItem(item)
                # 可选：展开
                item.setExpanded(True)
                self.statusbar.showMessage(f"Char '{target_char}' found and selected.")
                return
        # 没找到提示
        QMessageBox.information(None, "Not Found", f"Character '{target_char}' not found in the font data.")
        
    def render_font_preview(self):
        text = self.nfh_char_input_bar.toPlainText()
        if not text:
            return
        lines = text.splitlines()
        if len(lines) > 2:
            QMessageBox.warning(None, "Input Too Long", "Only the first 2 lines will be rendered to prevent performance issues.")
            text = "\n".join(lines[:2])
        
        # 拷贝一份背景图用于绘制预览，保持原图不变
        canvas = self.font_render_background_image.copy()
        draw = ImageDraw.Draw(canvas)
        
        # 绘制参数
        pen_x = 160
        baseline = 170
        SCALE_FIX = 64.0
        LINE_SPACING = 32

        for line in lines:
            if len(line) > 26:
                QMessageBox.warning(None, "Line Too Long", "Lines longer than 26 characters may not render correctly.\nExtra characters will be ignored.")
                line = line[:26]
            pen_x = 160 # 每行重置 x 坐标
            if self.show_border_checkbox.isChecked():
                # 画 baseline（调试用）
                canvas_w, canvas_h = canvas.size
                draw.line((0, baseline, canvas_w, baseline), fill=(0, 255, 0), width=1)
            
            for ch in line:
                glyph_data = self.glyphs.get(ch)
                if not glyph_data:
                    QMessageBox.warning(None, "Character Not Found", f"Character '{ch}' not found in glyph data.")
                    ch = '？'  # 替换为问号显示
                    glyph_data = self.glyphs.get(ch)
                
                # 从字形数据获取参数
                x = glyph_data.get("x", 0)
                y = glyph_data.get("y", 0)
                offsetx = glyph_data.get("offsetx", 0)
                offsety = glyph_data.get("offsety", 0)
                sizex = glyph_data.get("sizex", 0)
                sizey = glyph_data.get("sizey", 0)
                advancex = glyph_data.get("advancex", 0)
                
                # 从字体图集中裁剪字形图像
                glyph_image = self.font_image.crop((
                    x,
                    y,
                    x + sizex,
                    y + sizey
                ))
                # 用 alpha 直接生成黑色字形图像
                alpha = glyph_image.getchannel("A")
                glyph_image = Image.new("RGBA", glyph_image.size, (0, 0, 0, 0))
                glyph_image.putalpha(alpha)
                
                
                # 计算绘制位置
                draw_x = int(pen_x + offsetx / SCALE_FIX)
                draw_y = int(baseline - offsety / SCALE_FIX)
                
                # 粘贴字形图像到画布, 如果是 RGBA 图像则使用 alpha 通道作为掩码
                canvas.paste(
                    glyph_image,
                    (draw_x, draw_y),
                    glyph_image if glyph_image.mode == "RGBA" else None
                )
                # 调试边框
                if self.show_border_checkbox.isChecked():
                    draw.rectangle(
                        [draw_x, draw_y, draw_x + sizex, draw_y + sizey],
                        outline=(255, 0, 0)
                    )
                # 步进
                pen_x += advancex / SCALE_FIX
                
            baseline += LINE_SPACING # 每行增加基线间距
            
        self.display_image(image_meta={}, image=canvas)
        self.statusbar.showMessage("Font preview rendered.")
        
        
    
    def on_item_changed(self, item, column):
        if column != 1:
            return
        if getattr(self, "tree_mode", None) != "font":
            return
        parent = item.parent()
        if parent is None:
            return
        # 直接取 index 和 key
        idx = parent.data(0, Qt.UserRole)
        key = item.data(0, Qt.UserRole)
        if idx is None or key is None:
            return
        text = item.text(1)
        try:
            value = int(text)
        except ValueError:
            return
        self.glyphs[parent.text(0)][key] = value # 更新字形数据
        # 直接修改原数据
        self.nfh_json[idx][key] = value
        modify_nfh_item(self.nfh_file_data, self.nfh_json[idx]["blockOffset"], key, value)
        self.render_font_preview()

        


    def handle_convert_scb(self):
        """处理主菜单 Convert SCB点击事件"""    
        # 生成scb如果没有勾选字典提示警告
        if not self.cb_use_dict.isChecked():
            reply = QMessageBox.question(None, "Warning", "You Don't have Use Dict enabled. The converted SCB may not be correct. Proceed?", QMessageBox.Ok | QMessageBox.Cancel)
            if reply != QMessageBox.Ok:
                return
        
        json_filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Select JSON Files",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not json_filenames:
            return
        
        json_file_dir = os.path.dirname(json_filenames[0])
        output_dir = os.path.join(json_file_dir, "output_scb")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self._json_queue = list(json_filenames)
        self._json_total = len(json_filenames)
        self._json_count = 0
        
        def process_next():
            if not self._json_queue:
                self.statusbar.showMessage(
                    f"SCB conversion completed: {self._json_count}/{self._json_total}"
                )
                reply = QMessageBox.question(None, "Done", f"SCB conversion completed: {self._json_count}/{self._json_total}\nOutput directory: {output_dir}\nOpen the output directory?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    subprocess.Popen(["explorer", os.path.abspath(output_dir)])

                return
            json_filename = self._json_queue.pop(0)
            try:
                json_path = pathlib.Path(json_filename)
                output_scb_path = createSCB(
                    json_path, 
                    self.charMap['import'], 
                    self.cb_use_dict.isChecked(),
                    export_directory=output_dir
                )
                self._json_count += 1
                self.statusbar.showMessage(
                    f"Converted {json_path.name} to SCB ({self._json_count}/{self._json_total})"
                )
            except Exception as e:
                QMessageBox.warning(None, "Error", str(e))
            QTimer.singleShot(10, process_next)
        
        process_next()
        
        
    def handle_extract_scb(self):
        """处理主菜单 Extract SCB点击事件"""
        # 提取scb如果勾选字典提示警告
        if self.cb_use_dict.isChecked():
            reply = QMessageBox.question(None, "Warning", "You have Use Dict enabled. The exported SCB json may not be correct. Proceed?", QMessageBox.Ok | QMessageBox.Cancel)
            if reply != QMessageBox.Ok:
                return
        
        scb_filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Select SCB Files",
            "",
            "SCB Files (*.scb);;All Files (*)"
        )

        if not scb_filenames:
            return

        scb_file_dir = os.path.dirname(scb_filenames[0])
        output_dir = os.path.join(scb_file_dir, "output_json")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self._scb_queue = list(scb_filenames)
        self._scb_total = len(scb_filenames)
        self._scb_count = 0
        
        def process_next():
            if not self._scb_queue:
                self.statusbar.showMessage(
                    f"SCB export completed: {self._scb_count}/{self._scb_total}"
                )
                reply = QMessageBox.question(None, "Done", f"SCB export completed: {self._scb_count}/{self._scb_total}\nOutput directory: {output_dir}\nOpen the output directory?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    subprocess.Popen(["explorer", os.path.abspath(output_dir)])
                return
            scb_filename = self._scb_queue.pop(0)
            try:
                scb_path = pathlib.Path(scb_filename)
                script = scb.Scb.from_file(scb_path)
                os.makedirs(output_dir, exist_ok=True)
                output_json_path = exportJSON(
                    script,
                    scb_path,
                    self.charMap['export'],
                    self.cb_use_dict.isChecked(),
                    export_directory=output_dir
                )
                self._scb_count += 1
                self.statusbar.showMessage(
                    f"Exported {scb_path.name} ({self._scb_count}/{self._scb_total})"
                )
            except Exception as e:
                QMessageBox.warning(None, "Error", str(e))
            QTimer.singleShot(10, process_next)

        process_next()


    def handle_convert_dds(self, dds_format="DXT1A", nvdxt_path=None):
        #self.statusbar.showMessage(f"Convert DDS to {dds_format} is not implemented yet.")
        if not os.path.exists(nvdxt_path):
            QMessageBox.warning(None, "Error", f"nvdxt.exe not found.\nPlease put nvdxt.exe in {nvdxt_path}.")
            return

        png_files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PNG Files",
            "",
            "PNG Files (*.png);;All Files (*)"
        )
        if not png_files:
            return
        
        # 定义完成回调
        def on_finished(total):
            self.runner = None
            self.statusbar.showMessage(f"DDS conversion finished ({total} files)")
            reply = QMessageBox.information(None, "Done", f"DDS conversion completed for {total} files.\nOutput directory: {os.path.join(os.path.dirname(png_files[0]), 'output_dds')}\nOpen the output directory?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                subprocess.Popen(["explorer", os.path.abspath(os.path.join(os.path.dirname(png_files[0]), 'output_dds'))])
        
        def on_error(msg):
            self.runner = None
            self.statusbar.showMessage(f"DDS conversion failed.")
            QMessageBox.warning(None, "Error", f"DDS conversion failed: {msg}")
            
        
        self.runner = TaskRunner(self)
        self.runner.start(
            convert_png_to_dds_task,
            png_files,
            dds_format,
            nvdxt_path,
            on_progress=self.statusbar.showMessage,
            on_finished=on_finished,
            on_error=on_error
        )
        
        return
    
    def handle_build_char_map(self, zh2jp_kanji_map_path, original_nfh_json_path):
        if not os.path.exists(zh2jp_kanji_map_path):
            QMessageBox.warning(None, "Error", f"zh2jp_kanji_map.txt not found.\nPlease put zh2jp_kanji_map.txt in {zh2jp_kanji_map_path}.")
            return
        if not os.path.exists(original_nfh_json_path):
            QMessageBox.warning(None, "Error", f"Original NFH JSON file not found.\nPlease put im2_font.json in {os.path.dirname(original_nfh_json_path)}.")
            return
        
        
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Directory Containing JSON Files",
            ""
        )
        if not folder_path:
            return
        existing_char_map = FileOperations.load_char_map_from_file(zh2jp_kanji_map_path)
        fontdatas = json.load(open(original_nfh_json_path,"r", encoding="utf-8"))
        remaining_char_set = set()
        original_char_set = set()
        
        for fontdata in fontdatas:
            char = fontdata.get("char")
            if char < '㐂' or char > '鶴':
                remaining_char_set.add(char)
                continue
            original_char_set.add(char)
        
        def on_finished(result):
            self.runner = None
            output_dir = os.path.join(os.path.dirname(zh2jp_kanji_map_path), "output_char_map")
            os.makedirs(output_dir, exist_ok=True)
            output_mapIn = os.path.join(output_dir, "import.txt")
            output_mapOut = os.path.join(output_dir, "export.txt")
            output_mapReplace = os.path.join(output_dir, "zh2jp_kanji_map_replace.txt")
            new_char_map, replace_char_map = result
            with open(output_mapIn, 'w', encoding='utf-8') as f_in, \
                open(output_mapOut, 'w', encoding='utf-8') as f_out,\
                open(output_mapReplace, 'w', encoding='utf-8') as f_replace:
                for original_char, mapped_char in new_char_map.items():
                    f_in.write(f"{original_char}={mapped_char}\n")
                    f_out.write(f"{mapped_char}={original_char}\n")
                for original_char, mapped_char in replace_char_map.items():
                    f_replace.write(f"{original_char}={mapped_char}\n")
            self.statusbar.showMessage(f"Character remapping finished. {len(replace_char_map)} characters remapped.")
            reply = QMessageBox.information(None, "Done", f"Character remapping completed.\nTotal remapped characters: {len(replace_char_map)}\nOutput directory: {output_dir}\nOpen the output directory?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                subprocess.Popen(["explorer", os.path.abspath(output_dir)])
        
        def on_error(msg):
            self.runner = None
            self.statusbar.showMessage(f"Character remapping failed.")
            QMessageBox.warning(None, "Error", f"Character remapping failed: {msg}")

        self.runner = TaskRunner(self)
        self.runner.start(
            remap_chars_task,
            folder_path = folder_path,
            existing_char_map = existing_char_map,
            original_char_set = original_char_set,
            remaining_char_set = remaining_char_set,
            on_progress=self.statusbar.showMessage,
            on_finished=on_finished,
            on_error=on_error
        )
        return
        

    def handle_build_font_image_nfh(self, original_nfh_path = None, original_nfh_json_path = None, original_font_image_path = None, font_ttf_path = None):
        if not os.path.exists(original_nfh_path):
            QMessageBox.warning(None, "Error", f"Original NFH file not found.\nPlease put im2_font.nfh in {original_nfh_path}.")
            return
        if not os.path.exists(original_nfh_json_path):
            QMessageBox.warning(None, "Error", f"Original NFH JSON file not found.\nPlease put im2_font.json in {os.path.dirname(original_nfh_path)}.")
            return
        if not os.path.exists(original_font_image_path):
            QMessageBox.warning(None, "Error", f"Original font image not found.\nPlease put im2_font.png in {os.path.dirname(original_nfh_path)}.")
            return
        if not os.path.exists(font_ttf_path):
            QMessageBox.warning(None, "Error", f"Original font TTF file not found.\nPlease put DreamHanSans-W16.ttc in {os.path.dirname(original_nfh_path)}.")
            return

        nfh_data = bytearray()
        with open(original_nfh_path,"rb") as f:
            nfh_data.extend(f.read())

        fontdatas = json.load(open(original_nfh_json_path,"r", encoding="utf-8"))

        original_font_image = Image.open(original_font_image_path)
        
        def on_finished(result):
            self.runner = None
            # 保存结果
            output_dir = os.path.join(os.path.dirname(original_nfh_path), "output_font")
            os.makedirs(output_dir, exist_ok=True)
            nfh_data, canvas = result
            output_nfh_path = os.path.join(output_dir, "im2_font.nfh")
            output_font_image_path = os.path.join(output_dir, "im2_font.png")
            with open(output_nfh_path, "wb") as f:
                f.write(nfh_data)
            canvas.save(output_font_image_path)
            self.statusbar.showMessage("Font image build finished.")
            reply = QMessageBox.information(None, "Done", f"Font image and NFH build completed.\nOutput directory: {output_dir}\nOpen the output directory?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                subprocess.Popen(["explorer", os.path.abspath(output_dir)])
        
        def on_error(msg):
            self.runner = None
            self.statusbar.showMessage(f"Font image build failed.")
            QMessageBox.warning(None, "Error", f"Font image build failed: {msg}")
        
        self.runner = TaskRunner(self)
        self.runner.start(
            build_font_task,
            nfh_data = nfh_data,
            fontdatas = fontdatas,
            original_font_image = original_font_image,
            ttf_path = font_ttf_path,
            replace_char_map = self.charMap['export'], # export key = 原字符, value = 替换的汉化字符
            on_progress=self.statusbar.showMessage,
            on_finished=on_finished,
            on_error=on_error
        )
        return

    def handle_generate_nfh_json(self):
        nfh_filename, _ = QFileDialog.getOpenFileName(
            None, "Select NFH File", "", "NFH Files (*.nfh)"
        )
        if not nfh_filename:
            return

        with open(nfh_filename, 'rb') as f:
            nfh_data = bytearray(f.read())
            output_dir = os.path.dirname(nfh_filename)
            output_name = os.path.splitext(os.path.basename(nfh_filename))[0] + ".json"
            output_path = os.path.join(output_dir, output_name)
        
        def on_finished(json_data):
            self.runner = None
            with open(output_path, 'w', encoding='utf-8') as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)
            self.statusbar.showMessage(f"NFH JSON generated: {output_path}")
            reply = QMessageBox.information(None, "Done", f"NFH JSON generated successfully.\nOutput path: {output_path}\nOpen the output file?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                subprocess.Popen(["explorer", os.path.abspath(output_path)])
        
        def on_error(msg):
            self.runner = None
            self.statusbar.showMessage(f"NFH JSON generation failed.")
            QMessageBox.warning(None, "Error", f"NFH JSON generation failed: {msg}")
        
        self.runner = TaskRunner(self)
        self.runner.start(
            parse_nfh_task,
            nfh_data = nfh_data,
            on_progress=self.statusbar.showMessage,
            on_finished=on_finished,
            on_error=on_error
        )
        return
    
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
        item = self.treeWidget.itemAt(point)
        if item:
            item_meta = item.data(0, Qt.UserRole) or {}
            menu = QMenu(self)

            # 导入选项
            import_action = QAction("Replace", self)
            import_action.triggered.connect(lambda: self.handle_replace(item_meta))
            menu.addAction(import_action)

            # 针对xmb文件类型增加rewrite按钮
            # 判断规则：文件名后缀为.xmb（不区分大小写）
            name = item_meta.get('name', '')
            if isinstance(name, str) and name.lower().endswith('.xmb'):
                rewrite_action = QAction("Rewrite", self)
                rewrite_action.triggered.connect(lambda: self.handle_rewrite_xmb_item(item_meta))
                menu.addAction(rewrite_action)
                
                preview_xml_action = QAction("Preview XML", self)
                preview_xml_action.triggered.connect(lambda: self.preview_xmb_as_xml(item_meta))
                menu.addAction(preview_xml_action)

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

            menu.exec_(self.treeWidget.mapToGlobal(point))
        else:
            pass

    def preview_xmb_as_xml(self, item_meta: dict):
        """将 xmb 文件解析为 XML 并显示在预览区"""
        if item_meta is None:
            self.statusbar.showMessage("No item metadata available for XML preview.")
            return
        offset = item_meta.get('offset')
        size = item_meta.get('size')
        xmb_data = self.fileoperations.opened_file['data'][offset:offset+size]
        xml_tree, text_datas = xmb_to_xml(xmb_data)
        #xml_str = ET.tostring(xml_data.getroot(), encoding='utf-8').decode('utf-8')
        xml_text = xml_to_pretty_string(xml_tree)
        xmb_name = item_meta.get('name', 'preview.xmb')
        # 默认保存文件名为 xmb 文件同名的 json 文件，后缀改为 .json
        default_filename = os.path.splitext(xmb_name)[0] + '.json'
        show_xml_window(self, xml_text, text_datas, default_filename)
    
    
    def handle_rewrite_xmb_item(self, item_meta: dict):
        """处理 Rewrite 菜单点击事件（xmb专用）"""
        if item_meta is None:
            self.statusbar.showMessage("No item metadata available for Rewrite.")
            return
        
        rewrite_file_path, _ = QFileDialog.getOpenFileName(
            None, "Select Json File to Rewrite", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if not rewrite_file_path:
            return None
        
        json_file_name = os.path.splitext(os.path.basename(rewrite_file_path))[0]
        xmb_file_name = item_meta.get('name','').split('.')[0]
        if json_file_name != xmb_file_name :
            QMessageBox.warning(None, "Error", f"The selected JSON file name does not match the XMB file name.\nExpected: {xmb_file_name + '.json'}, Actual: {json_file_name}")
            return
        with open(rewrite_file_path, 'r', encoding='utf-16') as f:
            json_data = json.load(f)
        
        if not self.cb_use_dict.isChecked():
            reply = QMessageBox.question(None, "Warning", "You Don't have Use Dict enabled. The rewritten XMB may not be correct. Proceed?", QMessageBox.Ok | QMessageBox.Cancel)
            if reply != QMessageBox.Ok:
                return
        xmb_offset = item_meta['offset']
        xmb_size = item_meta['size']
        new_opened_file_data = bytearray(self.fileoperations.opened_file['data'])
        
        xmb_data = new_opened_file_data[xmb_offset:xmb_offset+xmb_size]
        
        try:
            xmb_data = self.fileoperations.rewrite_xmb_logic(
                xmb_data, 
                json_data, 
                self.charMap['import'], 
                self.cb_use_dict.isChecked())
        except Exception as e:
            QMessageBox.warning(None, "Error", f"Failed to rewrite XMB: {str(e)}")
            return   
        
        new_opened_file_data[xmb_offset:xmb_offset+xmb_size] = xmb_data
        self.fileoperations.opened_file['data'] = bytes(new_opened_file_data)
        self.statusbar.showMessage(f"Rewrite successful for: {item_meta.get('name')}")
        
    
    def handle_rewrite_xmb_file(self):
        """处理主菜单 Rewrite XMB 点击事件"""

        if not self.cb_use_dict.isChecked():
            reply = QMessageBox.question(None, "Warning", "You Don't have Use Dict enabled. The rewritten XMB may not be correct. Proceed?", QMessageBox.Ok | QMessageBox.Cancel)
            if reply != QMessageBox.Ok:
                return
        
        json_filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Select JSON Files to Rewrite XMB",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not json_filenames:
            return
        
        json_file_dir = os.path.dirname(json_filenames[0])
        output_dir = os.path.join(json_file_dir, "output_xmb")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self._json_queue = list(json_filenames)
        self._json_total = len(json_filenames)
        self._json_count = 0
        
        def process_next():
            if not self._json_queue:
                self.statusbar.showMessage(
                    f"XMB rewrite completed: {self._json_count}/{self._json_total}"
                )
                reply = QMessageBox.question(None, "Done", f"XMB rewrite completed: {self._json_count}/{self._json_total}\nOutput directory: {output_dir}\nOpen the output directory?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    subprocess.Popen(["explorer", os.path.abspath(output_dir)])
                return
            json_filename = self._json_queue.pop(0)
            try:
                json_path = pathlib.Path(json_filename)
                xmb_data = open(json_path.with_suffix('.xmb'), 'rb').read()
                xmb_data = bytearray(xmb_data)
                json_data = json.load(open(json_filename, 'r', encoding='utf-16'))
                xmb_data = self.fileoperations.rewrite_xmb_logic(
                    xmb_data,
                    json_data,
                    self.charMap['import'],
                    self.cb_use_dict.isChecked()
                )
                output_xmb_path = os.path.join(output_dir, json_path.with_suffix('.xmb').name)
                with open(output_xmb_path, 'wb') as f:
                    f.write(xmb_data)

                self._json_count += 1
                self.statusbar.showMessage(
                    f"Rewrote {json_path.name} to XMB ({self._json_count}/{self._json_total})"
                )
            except Exception as e:
                QMessageBox.warning(None, "Error", str(e))
            QTimer.singleShot(10, process_next)
        
        process_next()
    
        
    def handle_replace(self, item_meta: dict):
        """处理 Replace 菜单点击事件，并转发给核心逻辑"""
        if item_meta is None:
            self.statusbar.showMessage("No item metadata available for Replace.")
            return
        
        replaced_file_path, _ = QFileDialog.getOpenFileName(
            None, "Select File to Replace", "", "All Files (*)"
        )
        
        if not replaced_file_path:
            return None
        
        if '_RAW.dds' in item_meta.get('name','') :
            need_refresh = True
            try:
                self.fileoperations.replace_texture_logic(
                    replaced_file_path,
                    item_meta
                )
                success = True
            except Exception as e:
                QMessageBox.warning(None, "Error", f"Failed to replace texture: {str(e)}")
                return
        else:
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
            self.statusbar.showMessage("No item metadata available for Export.")
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
            """处理 Tools > Import from directory 点击事件（异步）"""
            if not self.fileoperations.opened_file.get('data'):
                QMessageBox.warning(self, "Warning", "No file is currently open.")
                return
        
            item_meta = self.treeWidget.topLevelItem(0).data(0, Qt.UserRole)
            
            imported_file_name = item_meta.get('name')
            
            directory = QFileDialog.getExistingDirectory(
                self, 
                "Select a directory to import files from",
                ""
            )
            
            if not directory:
                return
            
            try:
                imported_file_dict = {}
                isRecursive = False
                
                if os.path.exists(os.path.join(directory, f"{imported_file_name}.json")):
                    imported_file_dict = FileOperations.load_json_from_file(
                        os.path.join(directory, f"{imported_file_name}.json")
                    )
                    isRecursive = True
                elif os.path.exists(os.path.join(directory, f"{imported_file_name}_images.json")):
                    imported_file_dict = FileOperations.load_json_from_file(
                        os.path.join(directory, f"{imported_file_name}_images.json")
                    )
                else:
                    QMessageBox.warning(self, "Error", f"No import JSON file found for {imported_file_name} in the selected directory.")
                    return
                
                if imported_file_dict.get('parent_file') != item_meta.get('name'):
                    QMessageBox.warning(self, "Error", f"Import JSON parent file does not match the opened file.")
                    return
                
                # 初始化异步导入队列和计数
                self._import_queue = list(imported_file_dict.get('file_list', []))
                self._import_directory = directory
                self._import_count = 0
                self._import_total = len(self._import_queue)
                self._import_isRecursive = isRecursive
                
                if self._import_total == 0:
                    self.statusbar.showMessage("No files to import.")
                    return
                
                def process_next():
                    if not self._import_queue:
                        self.statusbar.showMessage(f"Import completed. Total {self._import_count} files imported.")
                        return
                    
                    file_info = self._import_queue.pop(0)
                    file_path = file_info.get('name')
                    file_offset = file_info.get('offset')
                    file_size = file_info.get('size')
                    
                    if file_size == 0:
                        QTimer.singleShot(10, process_next)
                        return
                    
                    if self._import_isRecursive:
                        file_path = file_info.get('path')
                    
                    full_file_path = os.path.join(self._import_directory, file_path)
                    
                    try:
                        if not os.path.exists(full_file_path):
                            self.statusbar.showMessage(f"Skipped (not found): {file_path}, {len(self._import_queue) + 1}/{self._import_total}")
                            QTimer.singleShot(10, process_next)
                            return
                        
                        if file_path.endswith(".dds"):
                            self.fileoperations.replace_texture_logic(
                                full_file_path,
                                {
                                    'offset': file_offset,
                                    'size': file_size,
                                }
                            )
                        else:
                            with open(full_file_path, 'rb') as f:
                                file_data = f.read()
                                if len(file_data) != file_size:
                                    QMessageBox.warning(self, "Error", f"File size mismatch for {file_path}. Expected {file_size}, got {len(file_data)}.")
                                    QTimer.singleShot(10, process_next)
                                    return
                                
                                self.fileoperations.replace_file_logic(
                                    {
                                        'offset': file_offset,
                                        'size': file_size,
                                    },
                                    file_data
                                )
                                
                        self._import_count += 1
                        remaining = len(self._import_queue)
                        self.statusbar.showMessage(f"Imported: {file_path}, {self._import_count}/{self._import_total}")
                    
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to import {file_path}: {str(e)}")
                    
                    QTimer.singleShot(10, process_next)
                
                process_next()
                
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
                if subitem is None:
                    continue
                #name = subitem.get('name')
                size = subitem.get('size', 0)
                if size == 0:
                    continue
                offset = subitem.get('offset', 0)
                ctype = subitem.get('type', 'file')
                path_name = subitem.get('path')
                if path_name is None:
                    continue
                else:
                    path_name = path_name.replace('/','+').replace('\\','+')
                

                if ctype == 'folder':
                    build_image_queue(subitem.get('subItem', []), current_dir, queue)
                elif ctype == 'file_image' and size > 0:
                    queue.append({
                        'name': path_name,
                        'size': size,
                        'offset': offset,
                    })
                elif ctype == 'file_texture' and size > 0:
                    queue.append({
                        'name': path_name,
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
       
    
    def handle_export_all_xmbs(self):
        """处理 Tools > Export all XMB 点击事件"""
        if not self.fileoperations.opened_file.get('data'):
            QMessageBox.warning(self, "Warning", "No file is currently open.")
            return
        
        item_meta = self.treeWidget.topLevelItem(0).data(0, Qt.UserRole)
        
        if item_meta is None:
            self.statusbar.showMessage("Please open a file first.")
            return
        
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select a directory to export XMBs to",
            ""
        )
        
        if not directory:
            return
        
        export_file_info ={
            "parent_file": item_meta.get('path').split('/')[0],
            "file_list": []
        }
        
        self._export_file_info = export_file_info
        # 注意导出的export_json_path包含_xmbs后缀
        self._export_json_path = os.path.join(directory, "{}_xmbs.json".format(item_meta.get('name')))
        self._export_count = 0
        self._export_total = 0
        self._export_dir = directory
    
        def count_xmbs(subitems):
            count = 0
            for subitem in subitems:
                ctype = subitem.get('type', 'file')
                size = subitem.get('size', 0)
                
                if ctype == 'folder':
                    count += count_xmbs(subitem.get('subItem', []))
                elif ctype == 'file_xmb' and size > 0 :
                    count += 1
                elif ctype in ['file_mpc', 'file_tsk', 'file_nut']:
                    count += count_xmbs(subitem.get('subItem', []))
            return count
        
        self._export_total = count_xmbs(item_meta.get('subItem', []))
        
        def build_xmb_queue(subitems, current_dir, queue):
            for subitem in subitems:
                if subitem is None:
                    continue
                name = subitem.get('name')
                size = subitem.get('size', 0)
                if size == 0:
                    continue
                offset = subitem.get('offset', 0)
                ctype = subitem.get('type', 'file')
                path_name = subitem.get('path')
                if path_name is None:
                    continue
                else:
                    path_name = path_name.replace('/','+').replace('\\','+')
                
                
                if ctype == 'folder':
                    build_xmb_queue(subitem.get('subItem', []), current_dir, queue)
                elif ctype == 'file_xmb' and size > 0 :
                    queue.append({
                        'name': path_name,
                        'size': size,
                        'offset': offset,
                    })
                elif ctype in ['file_mpc', 'file_tsk', 'file_nut']:
                    build_xmb_queue(subitem.get('subItem', []), current_dir, queue)
                else:
                    continue
        xmb_queue = []
        build_xmb_queue(item_meta.get('subItem', []), directory, xmb_queue)     
    
        def process_next():
            if not xmb_queue:
                FileOperations.save_json_to_file(self._export_file_info, self._export_json_path)
                self.statusbar.showMessage(f"Export all XMBs completed to directory: {directory}, total {self._export_count} XMB files.")
                return 
            file_item = xmb_queue.pop(0)
            name = file_item['name']
            size = file_item['size']
            offset = file_item['offset']
            
            try:
                if size == 0:
                    self._export_count += 1
                    QTimer.singleShot(10, process_next)
                    return
                file_data = self.fileoperations.opened_file["data"][offset:offset+size]
                save_path = os.path.join(self._export_dir, name)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                FileOperations.export_file_logic(file_data, save_path)
                self._export_file_info["file_list"].append({
                    "name": name,
                    "offset": offset,
                    "size": size,
                })
                self._export_count += 1
                self.statusbar.showMessage(f"Exported XMB: {name}, {self._export_count}/{self._export_total}")
            except Exception as e:
                self._export_count += 1
                self.statusbar.showMessage(f"Error exporting XMB {name}: {str(e)}")
                
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
            
    def display_image(self, image_meta, image=None):

        if image is None:
            offset = image_meta["offset"]
            size = image_meta ["size"]
            image_data = self.fileoperations.opened_file["data"][offset:offset+size]
            try:
                image = Image.open(io.BytesIO(image_data))
                width, height = image.size
            except Exception as e:
                self.preview_label.setText(f"Failed to load image: {str(e)}")
                return
        else:
            width, height = image.size
        
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
    
    # 重写 closeEvent 确保在关闭窗口时正确终止线程
    def closeEvent(self, event):
        if getattr(self, "runner", None):
            if self.runner.thread and self.runner.thread.isRunning():
                self.runner.thread.quit()
                self.runner.thread.wait()
        super().closeEvent(event)