import io
import struct
from core.readtool import *
from core.file_operations import *


# --- NUT 文件解析函数 ---
def load_nut_beta(data: bytes, nutfileName: str = "nut", baseOffset : int =0):
    """
    解析 NUT 并返回符合 item.json 的树形结构。
    """
    parsed = load_nut(data, nutfileName)
    entries = parsed.get("subfiles_info", [])

    def make_node(name, node_type, size=0, offset=0, baseOffset=baseOffset, extra=None):
        node = {"name": name, "type": node_type, "size": size, "offset": offset + baseOffset, "subItem": []}
        if extra:
            node.update(extra)
        return node

    root_path = ""
    root = make_node(nutfileName, "nut_file", len(data), 0)
    folder_nodes = {root_path: root}

    for ent in entries:
        folder = ent.get("folderpath", "") or ""
        # strip leading root folder name if present
        prefix = f"{nutfileName}/"
        if folder.startswith(prefix):
            folder = folder[len(prefix):]
        elif folder == nutfileName:
            folder = ""

        parts = [p for p in folder.split('/') if p]
        path_so_far = root_path
        for part in parts:
            path_so_far = f"{path_so_far}/{part}" if path_so_far else part
            if path_so_far not in folder_nodes:
                folder_nodes[path_so_far] = make_node(part, "folder")

        parent_path = folder if folder else root_path
        
        filename = ent.get("filename", "")
        filetype = FileOperations.get_file_type(filename)
        
        file_node = make_node(
            ent.get("filename", ""),
            filetype,
            ent.get("filesize", 0),
            ent.get("fileoff", 0),
            extra={
                "width": ent.get("width"),
                "height": ent.get("height"),
                "texFmt": ent.get("texFmt"),
            }
        )
        folder_nodes[parent_path]["subItem"].append(file_node)

    # Attach folders to parents
    for path in sorted(folder_nodes.keys(), key=lambda p: p.count("/")):
        if path == root_path:
            continue
        parent_path = path.rsplit("/", 1)[0] if "/" in path else root_path
        parent = folder_nodes.get(parent_path, root)
        current = folder_nodes[path]
        if not any(item["name"] == current["name"] and item["type"] == "folder" for item in parent["subItem"]):
            parent["subItem"].append(current)

    def propagate(node):
        if "file" in node["type"]:
            return node["size"], node["offset"]
        total = 0
        min_off = None
        for child in node["subItem"]:
            c_size, c_off = propagate(child)
            total += c_size
            if c_off and (min_off is None or c_off < min_off):
                min_off = c_off
        node["size"] = total
        if min_off is not None:
            node["offset"] = min_off
        return node["size"], node["offset"]

    propagate(root)
    '''
    with open("debug_nut_tree.json", "w", encoding="utf-8") as f:
        import json
        json.dump(root, f, indent=4, ensure_ascii=False)
    '''
    
    def sort_by_offset(node):
        node['subItem'].sort(key=lambda x: x.get('offset', 0))
        for child in node['subItem']:
            if child.get('subItem'):
                sort_by_offset(child)
                
    sort_by_offset(root)
    
    return root




def load_nut(data, nutfileName="nut"):
    f = io.BytesIO(data)
    try:
        magic = f.read(4).decode('ascii')
    except UnicodeDecodeError:
        magic = "ERROR"
    if magic != "NTP3":
        return {
            "file_size": len(data),
            "file_nums": 0,
            "subfiles_info": []
        }
        #raise Exception("Invalid NUT file")
    version = read_short(f)
    texCount = read_short(f)
    f.seek(0x10, 0) # ABS
    
    nut_file_info = []
    for i in range(0,texCount):
        offset = f.tell()
        chunkSize = read_long(f)
        unk = read_long(f)
        textSize = read_long(f)
        headerSize = read_short(f)
        '''
            0：从文件的开头开始计算（默认值）。
            1：从文件的当前位置开始计算。
            2：从文件的末尾开始计算。
        '''
        f.seek(0x4, 1)
        texType = read_short(f)
        width = read_short(f)
        height = read_short(f)
        f.seek(0x8,1)
        texOffset = read_long(f)
        f.seek(offset+headerSize-0x08, 0)
        texID = read_long(f)
        f.seek(0x4, 1)
        if version == 0x200:
            f.seek(offset+texOffset, 0)
        texDataOffset = f.tell()
        texData = f.read(textSize)
        texFmt = ""
        
        if texType == 0:
            texFmt = "DXT1"
        elif texType == 1:
            texFmt = "DXT3"
        elif texType == 2:
            texFmt = "DXT5"
        else:
            texFmt = "RAW"
        
        fileName = "{0}_{1}x{2}_{3}.dds".format(texID, width, height, texFmt)

        nut_file_info.append({
            'filename': fileName,
            'folderpath': nutfileName,
            'absfilepath': nutfileName+"/"+fileName,
            'fileoff': texDataOffset,
            'filesize':textSize,
            'width': width,
            'height': height,
            'texFmt': texFmt
        })

        if version == 0x200:
            f.seek(offset+headerSize, 0)
        else:
            f.seek(offset+chunkSize, 0)
    nut_info ={
        "file_size": len(data),
        "file_nums": texCount,
        "subfiles_info": nut_file_info
    }
    return nut_info