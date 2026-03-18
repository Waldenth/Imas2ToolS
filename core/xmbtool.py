import struct
import json
import os
import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QMenuBar, QAction, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt
from xml.dom import minidom

def xml_to_pretty_string(tree: ET.ElementTree):
    rough_string = ET.tostring(tree.getroot(), encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")
    #pretty_xml = reparsed.toprettyxml(indent="  ")
    #return "\n".join(pretty_xml.split("\n")[1:])

def show_xml_window(parent, xml_text, text_datas=None, default_filename="preview_xmb.json"):
    dialog = QDialog(parent)
    filename_not_ext = os.path.splitext(default_filename)[0]
    dialog.setWindowTitle(f"XML Preview: {filename_not_ext}")
    dialog.resize(700, 600)

    layout = QVBoxLayout(dialog)

    # ===== 菜单栏 =====
    menubar = QMenuBar(dialog)
    file_menu = menubar.addMenu("File")

    save_json_action = QAction("Save texts as JSON", dialog)
    save_xml_action = QAction("Save XML", dialog)
    file_menu.addAction(save_json_action)
    file_menu.addAction(save_xml_action)
    layout.setMenuBar(menubar)

    # ===== XML 显示区 =====
    text_edit = QTextEdit()
    text_edit.setReadOnly(True)
    text_edit.setPlainText(xml_text)

    layout.addWidget(text_edit)
    
    # ===== 保存 JSON 功能 =====
    def save_json():
        if not text_datas:
            reply = QMessageBox.question(parent, "No text data", "No text data available to save as JSON. Confirm to save empty JSON?", QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        file_path, _ = QFileDialog.getSaveFileName(
            dialog,
            "Save JSON",
            default_filename,
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(text_datas, f, ensure_ascii=False, indent=4)

    def save_xml():
        file_path, _ = QFileDialog.getSaveFileName(
            dialog,
            "Save XML",
            default_filename.replace('.json', '.xml'),
            "XML Files (*.xml);;All Files (*)"
        )

        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(xml_text)

    save_json_action.triggered.connect(save_json)
    save_xml_action.triggered.connect(save_xml)

    dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    dialog.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)

    dialog.exec_()

    

def xmb_to_xml(xmb_data):
    data = xmb_data
    
    # -------------------------
    # 大端读取函数
    # -------------------------
    def u32(o): return struct.unpack(">I", data[o:o+4])[0]
    def i32(o): return struct.unpack(">i", data[o:o+4])[0]
    def i16(o): return struct.unpack(">h", data[o:o+2])[0]

    # -------------------------
    # 读取 UTF8 字符串
    # -------------------------
    def read_utf8(offset):
        s = b""
        while data[offset] != 0:
            s += data[offset:offset+1]
            offset += 1
        return s.decode("utf-8")

    # -------------------------
    # 读取 UTF16-BE 字符串
    # -------------------------
    def read_utf16(offset):
        chars = []
        size = 0
        while True:
            c = data[offset:offset+2]
            if c == b'\x00\x00':
                break
            chars.append(c)
            offset += 2
            size += 2
        return b''.join(chars).decode("utf-16-be"), size

    # -------------------------
    # header
    # -------------------------
    magic = u32(0)
    if magic != 1481458208:
        raise Exception("Invalid XMB file")

    numelements = i32(4)
    numattributes = i32(8)

    elementoffset = i32(24)
    attributeoffset = i32(28)
    localnamestartoffset = i32(36)
    valuenamestartoffset = i32(40)

    elementnameoffset = i32(elementoffset)

    attributeamount = i16(elementoffset + 4)
    childelementamount = i16(elementoffset + 6)

    attributeindexstart = i16(elementoffset + 8)
    elementindexstart = i16(elementoffset + 10)

    # -------------------------
    # ValueData 记录
    # -------------------------
    value_datas = []

    # -------------------------
    # Entry 结构
    # -------------------------
    class Entry:
        def __init__(self):
            self.name = ""
            self.children = []
            self.attributes = []
            self.num_attr = 0
            self.num_child = 0
            self.attr_start = 0
            self.elem_start = 0

    # -------------------------
    # 递归扫描
    # -------------------------
    def scan(parent):

        base = elementoffset + parent.elem_start * 16

        for i in range(parent.num_child):

            off = base + i * 16

            child = Entry()

            name_offset = i32(off)
            child.num_attr = i16(off+4)
            child.num_child = i16(off+6)
            child.attr_start = i16(off+8)
            child.elem_start = i16(off+10)

            child.name = read_utf8(name_offset + localnamestartoffset)

            # attributes
            for a in range(child.num_attr):

                aoff = attributeoffset + (a + child.attr_start) * 8

                name_offset = i32(aoff)
                value_offset = i32(aoff+4)

                attr_name = read_utf8(name_offset + localnamestartoffset)

                if attr_name == "_text":

                    offset = value_offset + valuenamestartoffset

                    text, size = read_utf16(offset)

                    value_datas.append({
                        "_offset": offset,
                        "_offsetHex": hex(offset),
                        "_text": text,
                        "_size": size
                    })

                    attr_value = text

                else:

                    attr_value = read_utf8(value_offset + valuenamestartoffset)

                child.attributes.append((attr_name, attr_value))

            scan(child)

            parent.children.append(child)

    # -------------------------
    # 构建 XML
    # -------------------------
    def build_xml(entry):

        node = ET.Element(entry.name)

        for k,v in entry.attributes:
            node.set(k, v)

        for c in entry.children:
            node.append(build_xml(c))

        return node

    # -------------------------
    # root entry
    # -------------------------
    root = Entry()

    root.name = read_utf8(elementnameoffset + localnamestartoffset)

    root.num_attr = attributeamount
    root.num_child = childelementamount
    root.attr_start = attributeindexstart
    root.elem_start = elementindexstart

    # root attributes
    for i in range(root.num_attr):

        off = attributeoffset + (i + root.attr_start) * 8

        name_offset = i32(off)
        value_offset = i32(off+4)

        name = read_utf8(name_offset + localnamestartoffset)
        value = read_utf8(value_offset + valuenamestartoffset)

        root.attributes.append((name, value))

    scan(root)

    # -------------------------
    # 输出 XML
    # -------------------------
    tree = ET.ElementTree(build_xml(root))

    return tree, value_datas