import os
import json

def is_emoji(c):
    if ord(c) in range(0xE000, 0xE100):
        return True
    return False

def remap_chars_task(progress, folder_path, existing_char_map = {}, original_char_set = set(), remaining_char_set = set()):
    '''
    existing_char_map: zh2jp_kanji_map中已存在的简体汉字 - 同义日文kanji映射, key是简体汉字, value是日文kanji
    original_char_set: 原始字体中包含的所有kanji字符集合
    '''
    # escape_char_set: 占位符字符和日文需用字集合，这些字符不进行映射，直接保留原样。
    escape_char_set =set(
        ['','','','','','','','','','','','','','','', \
         '歩','槻','覇','響','玲','県','茨','栃','岐','阜','広','札','幌','潟','沢']
    )
        
    used_char_set = set(existing_char_map.values())

    # 可用于映射的字符集合 = 原始字体中包含的所有kanji字符集合 - 已经被使用的字符集合
    available_char_set = set()
    for c in original_char_set:
        if c not in used_char_set:
            available_char_set.add(c)
    
    if len(available_char_set) == 0:
        raise ValueError("No available characters left for remapping.")
    
    progress("Collecting Json files hanzi characters...")
    need_remap_char_set = collect_translate_chars(folder_path)
    missing_char_list = [c for c in need_remap_char_set if c not in existing_char_map.keys()]
    if len(missing_char_list) > len(available_char_set):
        raise ValueError(f"Not enough available characters for remapping. Need {len(missing_char_list)}, but only {len(available_char_set)} available.")
    count = 0
    replace_char_map = {}
    progress("Remapping characters...")
    
    # 移除占位符字符（不进行映射）
    for c in escape_char_set:
        if c in missing_char_list:
            missing_char_list.remove(c)

    # 先移除掉需要映射的字符和可用于映射的字符的交集 ，以及emoji字符（不进行映射）
    for c in missing_char_list[:]:
        if c in available_char_set:
            available_char_set.remove(c)
            missing_char_list.remove(c)
        elif is_emoji(c):
            missing_char_list.remove(c)
    
    for c in missing_char_list:
        if 0xE000 <= ord(c) and ord(c) <= 0xF8FF:
            raise ValueError(f"Character {c} , codepoint: {ord(c)} is in the Unicode Private Use Area, which is not allowed for remapping.")
        if c in remaining_char_set:
            pass
        else:
            existing_char_map[c] = available_char_set.pop()
            replace_char_map[c] = existing_char_map[c]
        count += 1
        #progress(f"Remapping characters:  {c}=>{existing_char_map[c]} , ({count}/{len(missing_char_list)})")
    
    return (existing_char_map, replace_char_map)


def collect_translate_chars(folder_path):
    char_set = set()
    file_count = 0

    for root, _, files in os.walk(folder_path):
        for file in files:
            if not file.lower().endswith(".json"):
                continue

            json_path = os.path.join(root, file)

            try:
                with open(json_path, "r", encoding="utf-16") as f:
                    data = json.load(f)

                # 情况1：字典类型，存在 "translate" 列表
                if isinstance(data, dict) and "translate" in data:
                    translates = data.get("translate", [])
                    if isinstance(translates, list):
                        file_count += 1
                        for text in translates:
                            if isinstance(text, str):
                                char_set.update(text)
                # 情况2：列表类型，每个元素是字典，含 "translate" 字段
                elif isinstance(data, list):
                    has_translate = False
                    for item in data:
                        if isinstance(item, dict) and "translate" in item:
                            t = item["translate"]
                            if isinstance(t, str):
                                char_set.update(t)
                                has_translate = True
                    
                    if has_translate:
                        file_count += 1

            except Exception as e:
                raise RuntimeError(f"Failed to process {json_path}: {e}")

    return char_set