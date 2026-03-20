# core/tsktool.py

import io
import pathlib
from core.readtool import *
from core.file_operations import *

# --- TSK 文件解析函数 ---
def load_tsk_beta(data: bytes, tskfileName: str = "tsk", baseOffset : int =0):
    """
    解析 TSK 文件并直接返回与 item.json 相同的树形结构，不依赖 load_tsk。
    """
    file = io.BytesIO(data)

    # Header parsing
    file.seek(0)
    _tsk_magic = read_long(file)
    file_count = read_long(file)

    file_sizes = []
    file_offsets = []
    for _ in range(file_count):
        file_sizes.append(read_long(file))
        file_offsets.append(read_long(file))

    # XMB section positions
    xmb_start = file_offsets[0]
    file.seek(xmb_start)
    file.seek(0x4, 1)
    info_entries = read_long(file)
    file.seek(0x10, 1)
    info_offset = read_long(file)
    info_list = read_long(file)
    file.seek(0x4, 1)
    command_offset = read_long(file)
    name_offset = read_long(file)

    # Parse file names (mirrors original algorithm, but kept local)
    names = [f"{tskfileName}.xmb"]
    file.seek(xmb_start)
    file.seek(info_offset, 1)

    TMP2 = None
    for i in range(info_entries):
        file.seek(0x4, 1)
        info_count = read_short(file)
        file.seek(0xA, 1)
        tmp_info_pos = file.tell()

        if i == 0:
            file.seek(xmb_start)
            file.seek(info_list, 1)
            TMP2 = file.tell()
        else:
            file.seek(TMP2)

        for _ in range(info_count):
            command_start = read_long(file)
            name_start = read_long(file)
            TMP2 = file.tell()

            file.seek(xmb_start)
            file.seek(command_offset + command_start, 1)
            command = read_varstring(file)

            file.seek(xmb_start)
            file.seek(name_offset + name_start, 1)
            sname = read_varstring(file)

            # Match the legacy logic: path -> SPATH, name -> FNAME, index -> append
            if command == "path":
                SPATH = sname
            elif command == "name":
                FNAME = sname
            elif command == "index":
                if SPATH == ".":
                    names.append(FNAME)
                else:
                    names.append(SPATH + FNAME)

            file.seek(TMP2)

        file.seek(tmp_info_pos)

    # Build flat file entries
    entries = []
    for idx in range(file_count):
        composed = f"{tskfileName}/{names[idx]}"
        file.seek(file_offsets[idx])
        header = read_long(file)

        if header == 0x7A6C6962:  # "zlib"
            _size = read_long(file)
            zsize = read_long(file)
            data_offset = file.tell()
            size_to_use = zsize
        else:
            size_to_use = file_sizes[idx]
            data_offset = file_offsets[idx]

        folder = str(pathlib.Path(composed).parent)
        name = pathlib.Path(composed).name

        prefix = f"{tskfileName}/"
        if folder.startswith(prefix):
            folder = folder[len(prefix):]
        elif folder == tskfileName:
            folder = ""

        entries.append({
            "filename": name,
            "folder": folder,
            "size": size_to_use,
            "offset": data_offset + baseOffset
        })

    def make_node(name, node_type, size=0, offset=0):
        return {"name": name, "type": node_type, "size": size, "offset": offset, "subItem": []}

    root_path = ""
    folder_nodes = {root_path: make_node(f"{tskfileName}.tsk", "tsk_file", len(data), 0)}

    for entry in entries:
        parts = [p for p in entry["folder"].split("/") if p]
        path_so_far = root_path

        for part in parts:
            path_so_far = f"{path_so_far}/{part}" if path_so_far else part
            if path_so_far not in folder_nodes:
                folder_nodes[path_so_far] = make_node(part, "folder")

        parent_path = entry["folder"] if entry["folder"] else root_path
        file_type = FileOperations.get_file_type(entry["filename"])
        file_node = make_node(entry["filename"], file_type, entry["size"], entry["offset"])
        folder_nodes[parent_path]["subItem"].append(file_node)

    for path in sorted(folder_nodes.keys(), key=lambda p: p.count("/")):
        if path == root_path:
            continue
        parent_path = path.rsplit("/", 1)[0] if "/" in path else root_path
        parent = folder_nodes.get(parent_path, folder_nodes[root_path])
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

    propagate(folder_nodes[root_path])
    
    '''
    with open("debug_tsk_tree.json", "w", encoding="utf-8") as f:
        import json
        json.dump(folder_nodes[root_path], f, indent=4, ensure_ascii=False)
    '''
    
    def sort_by_offset(node):
        node['subItem'].sort(key=lambda x: x.get('offset', 0))
        for child in node['subItem']:
            if child.get('subItem'):
                sort_by_offset(child)
    
    sort_by_offset(folder_nodes[root_path])
    
    return folder_nodes[root_path]



# --- 旧版 TSK 文件解析函数 (保留以备参考) ---
def load_tsk(data, tskfileName="tsk"):
    file = io.BytesIO(data)
    file.seek(0)
    TSK = read_long(file)
    FILES = read_long(file)
    FILESIZE = []
    FILEOFFSET = []
    for _ in range(FILES):
        FILESIZE.append(read_long(file))
        FILEOFFSET.append(read_long(file))
    XMBSTART = FILEOFFSET[0]
    file.seek(XMBSTART)
    file.seek(0x4, 1)
    INFO = read_long(file)
    file.seek(0x10, 1)
    INFOOFFSET = read_long(file)
    INFOLIST = read_long(file)
    file.seek(0x4, 1)
    COMMANDOFFSET = read_long(file)
    NAMEOFFSET = read_long(file)
    x = 0
    BASE = tskfileName
    BASE += ".xmb"
    NAMES = [BASE]
    x += 1
    file.seek(XMBSTART)
    file.seek(INFOOFFSET, 1)
    for i in range(INFO):
        file.seek(0x4, 1)
        INFOCOUNT = read_short(file)
        file.seek(0xA, 1)
        TMP1 = file.tell()
        if i == 0:
            file.seek(XMBSTART)
            file.seek(INFOLIST, 1)
            TMP2 = file.tell()
        else:
            file.seek(TMP2)
        for _ in range(INFOCOUNT):
            COMMANDSTART = read_long(file)
            NAMESTART = read_long(file)
            TMP2 = file.tell()
            file.seek(XMBSTART)
            file.seek(COMMANDOFFSET + COMMANDSTART, 1)
            COMMAND = read_varstring(file)
            file.seek(XMBSTART)
            file.seek(NAMEOFFSET + NAMESTART, 1)
            SNAME = read_varstring(file)
            if COMMAND == "path":
                SPATH = SNAME
            elif COMMAND == "name":
                FNAME = SNAME
            elif COMMAND == "index":
                if SPATH == ".":
                    NAMES.append(FNAME)
                else:
                    SPATH += FNAME
                    NAMES.append(SPATH)
            file.seek(TMP2)
        file.seek(TMP1)
    x = 0
    
    tsk_file_info = []
    for i in range(FILES):
        NAME2 = tskfileName
        NAME2 += "/"
        NAME2 += NAMES[x]
        x += 1
        file.seek(FILEOFFSET[i])
        HEADER = read_long(file)
        if HEADER == 0x7a6c6962:
            SIZE = read_long(file)
            ZSIZE = read_long(file)
            FILEOFF = file.tell()
            cur_file_folder = str(pathlib.Path(NAME2).parent)
            cur_file_name = pathlib.Path(NAME2).name
            
            tsk_file_info.append({
                "filename": cur_file_name,
                "folderpath": cur_file_folder,
                "absfilepath": NAME2,
                "fileoff": FILEOFF,
                "filesize": ZSIZE
            })
            
            
        else:
            cur_file_folder = str(pathlib.Path(NAME2).parent)
            cur_file_name = pathlib.Path(NAME2).name
            tsk_file_info.append({
                "filename": cur_file_name,
                "folderpath": cur_file_folder,
                "absfilepath": NAME2,
                "fileoff": FILEOFFSET[i],
                "filesize": FILESIZE[i]
            })
    tsk_info ={
        "file_size": len(data),
        "file_nums": FILES,
        "subfiles_info": tsk_file_info
    }
    return tsk_info