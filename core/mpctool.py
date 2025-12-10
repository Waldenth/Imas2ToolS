# core/mpctool.py

import io
import struct
from core.readtool import *
from core.file_operations import *
# --- MPC 文件解析函数 ---


def load_mpc_beta(data: bytes, mpcfileName="mpc", baseOffset : int =0):
    """
    解析 MPC 文件数据，返回树形结构的 JSON 格式（类似 item.json 样式）。
    完全独立解析，不复用 load_mpc。
    :param data: MPC 文件的完整字节数据
    :param mpcfileName: 主 MPC 文件的名称
    :return: 包含树形结构的字典
    """
    f = io.BytesIO(data)
    
    # === Header Reading ===
    f.seek(0x04)
    unk = read_long(f)
    size = read_long(f)
    files = read_long(f)
    f.seek(0x30)
    infostart = read_long(f)
    msgstart = read_long(f)
    datastart = read_long(f)
    
    # === 读取文件信息块 ===
    f.seek(infostart)
    file_info = []
    
    for _ in range(files):
        f.seek(0x8, 1)
        filesize = read_long(f)
        fileoffset = read_long(f)
        filenameid = read_long(f)
        filefolderid = read_long(f)
        f.seek(0x8, 1)
        
        file_info.append({
            'filesize': filesize,
            'fileoffset': fileoffset,
            'filenameid': filenameid,
            'filefolderid': filefolderid
        })
    
    # === 读取字符串表 ===
    f.seek(msgstart)
    f.seek(0x20, 1)
    
    msg = f.tell()
    names = read_short(f)
    f.seek(0x6, 1)
    names_array = read_short(f)
    names_start = read_short(f)
    
    f.seek(msg + names_array)
    
    name_sizes = []
    name_offsets = []
    
    for _ in range(names):
        name_sizes.append(read_long(f))
        name_offsets.append(read_long(f))
    
    name_strings = []
    for i in range(names):
        f.seek(msg + names_start + name_offsets[i])
        name_strings.append(read_string(f, name_sizes[i]))
    
    # === 构建树形结构 ===
    # 字典用于存储路径->节点的映射
    path_nodes = {}
    all_files = []
    
    # 首先收集所有文件信息
    for i in range(files):
        filename = name_strings[file_info[i]['filenameid']]
        folderpath = name_strings[file_info[i]['filefolderid']]
        filesize = file_info[i]['filesize']
        fileoff = file_info[i]['fileoffset'] + datastart + baseOffset
        
        all_files.append({
            'filename': filename,
            'folderpath': folderpath if folderpath and folderpath != '.' else '',
            'filesize': filesize,
            'fileoff': fileoff
        })
    
    # 创建文件夹节点和文件节点
    def create_node(name, node_type, size=0, offset=0):
        """创建一个节点"""
        return {
            'name': name,
            'type': node_type,
            'size': size,
            'offset': offset,
            'subItem': []
        }
    
    # 构建文件树
    root_path = ''
    # 将根视为文件夹以便汇总子项尺寸
    folder_nodes = {root_path: create_node(mpcfileName, 'file_mpc', size, 0)}
    
    # 处理所有文件，创建必要的文件夹
    for file_entry in all_files:
        folderpath = file_entry['folderpath']
        
        # 确保所有父文件夹都存在
        if folderpath:
            path_parts = folderpath.strip('/').split('/')
            current_path = ''
            
            for part in path_parts:
                if current_path:
                    current_path += '/' + part
                else:
                    current_path = part
                
                if current_path not in folder_nodes:
                    folder_nodes[current_path] = create_node(part, 'folder')
        
        # 添加文件到对应文件夹
        file_type = FileOperations.get_file_type(file_entry['filename'])
        file_node = create_node(
            file_entry['filename'],
            file_type,
            file_entry['filesize'],
            file_entry['fileoff']
        )
        
        if folderpath:
            folder_nodes[folderpath]['subItem'].append(file_node)
        else:
            folder_nodes[root_path]['subItem'].append(file_node)
    
    # 构建文件夹的父子关系
    def build_folder_hierarchy(folder_dict):
        """递归构建文件夹层级"""
        for path, node in sorted(folder_dict.items()):
            if path == root_path:
                continue
            
            # 找到该文件夹的父路径
            if '/' in path:
                parent_path = '/'.join(path.split('/')[:-1])
                if parent_path in folder_dict:
                    # 检查这个文件夹是否已经添加到父节点
                    is_added = any(item['name'] == node['name'] and item['type'] == 'folder' 
                                  for item in folder_dict[parent_path]['subItem'])
                    if not is_added:
                        folder_dict[parent_path]['subItem'].append(node)
            else:
                # 直接在根目录下
                is_added = any(item['name'] == node['name'] and item['type'] == 'folder' 
                              for item in folder_dict[root_path]['subItem'])
                if not is_added:
                    folder_dict[root_path]['subItem'].append(node)
    
    build_folder_hierarchy(folder_nodes)
    
    # 计算文件夹大小
    def calculate_folder_size(node):
        """递归计算文件夹大小"""
        if node['type'] not in ['folder', 'file_mpc']:
            return node['size']

        total_size = 0
        min_offset = None

        for sub_item in node['subItem']:
            size = calculate_folder_size(sub_item)
            total_size += size
            sub_off = sub_item.get('offset')
            if sub_off is not None:
                if min_offset is None:
                    min_offset = sub_off
                else:
                    min_offset = min(min_offset, sub_off)

        node['size'] = total_size
        if min_offset is not None:
            node['offset'] = min_offset

        return total_size
    
    # 计算所有文件夹的大小
    root_node = folder_nodes[root_path]
    calculate_folder_size(root_node)

    # 按 offset 从小到大排序所有层级的 subItem，便于查看顺序
    def sort_by_offset(node):
        node['subItem'].sort(key=lambda x: x.get('offset', 0))
        for child in node['subItem']:
            if child.get('subItem'):
                sort_by_offset(child)

    sort_by_offset(root_node)
    
    '''
    with open("debug_mpc_tree.json", "w", encoding="utf-8") as debug_file:
        import json
        json.dump(root_node, debug_file, ensure_ascii=False, indent=4)
    '''
    
    return root_node






# --- 旧版 MPC 文件解析函数 (保留以备参考) ---
def load_mpc(data: bytes, mpcfileName="mpc"):
    """
    解析 MPC 文件数据，返回内部子文件信息。
    :param data: MPC 文件的完整字节数据
    :param mpcfileName: 主 MPC 文件的名称
    :return: 包含所有子文件信息的字典
    """
    f = io.BytesIO(data)
    
    # Header Reading (忽略未使用的变量，只读取需要的)
    f.seek(0x04) # 跳过 PAC
    unk = read_long(f)
    size = read_long(f)
    files = read_long(f)
    f.seek(0x30)
    infostart = read_long(f)
    msgstart = read_long(f)
    datastart = read_long(f)
    f.seek(infostart)
    
    file_info = []
    
    # 1. 读取文件信息块 (File Info)
    for _ in range(files):
        f.seek(0x8, 1)  # Skip 8 bytes
        filesize = read_long(f)
        fileoffset = read_long(f)
        filenameid = read_long(f)
        filefolderid = read_long(f)
        f.seek(0x8, 1)  # Skip another 8 bytes
        
        file_info.append({
            'filesize': filesize,
            'fileoffset': fileoffset,
            'filenameid': filenameid,
            'filefolderid': filefolderid
        })
    
    # 2. 读取文件名/文件夹名信息块 (String Table)
    f.seek(msgstart)
    f.seek(0x20, 1)
    
    msg = f.tell()
    names = read_short(f)
    f.seek(0x6, 1)
    names_array = read_short(f)
    names_start = read_short(f)
    
    f.seek(msg + names_array)
    
    name_sizes = []
    name_offsets = []
    
    # 读取名称大小和偏移量
    for _ in range(names):
        name_sizes.append(read_long(f))
        name_offsets.append(read_long(f))
    
    name_strings = []
    
    # 读取实际名称字符串
    for i in range(names):
        f.seek(msg + names_start + name_offsets[i])
        name_strings.append(read_string(f, name_sizes[i]))
    
    # 3. 组合信息
    mpc_file_info = []
    for i in range(files):
        filename = name_strings[file_info[i]['filenameid']]
        folderpath = name_strings[file_info[i]['filefolderid']]
        # 修正：通常根目录路径为空或'.'，这里避免 '//' 出现
        if folderpath and folderpath != '.':
            absfilepath = folderpath + '/' + filename
        else:
            absfilepath = filename

        fileoff = file_info[i]['fileoffset'] + datastart
        filesize = file_info[i]['filesize']
        
        mpc_file_info.append({
            'filename': filename,
            'folderpath': folderpath,
            'absfilepath': absfilepath,
            'fileoff': fileoff,
            'filesize': filesize,
            'filenameid': file_info[i]['filenameid'],
            'filefolderid': file_info[i]['filefolderid']
        })
        
    mpc_info= {
        "mpc_name": mpcfileName,
        "file_size": size,
        "file_nums": files,
        "infostart": infostart,
        "msgstart": msgstart,
        "datastart": datastart,
        "subfiles_info": mpc_file_info
    }
    
    return mpc_info
