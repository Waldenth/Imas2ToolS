import os
import json

def remap_chars_task(progress, folder_path, existing_char_map = {}, original_char_set = set(), remaining_char_set = set()):
    '''
    existing_char_map: zh2jp_kanji_map中已存在的简体汉字 - 同义日文kanji映射, key是简体汉字, value是日文kanji
    original_char_set: 原始字体中包含的所有kanji字符集合
    '''
    escape_char_set =set(
        ['','','','','','','','','','','','','','','']
    )
        
    used_char_set = set(existing_char_map.values())

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
    
    for c in escape_char_set:
        if c in missing_char_list:
            missing_char_list.remove(c)

    for c in missing_char_list[:]:
        if c in available_char_set:
            available_char_set.remove(c)
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
    string_count = 0

    for root, _, files in os.walk(folder_path):
        for file in files:
            if not file.lower().endswith(".json"):
                continue

            json_path = os.path.join(root, file)

            try:
                with open(json_path, "r", encoding="utf-16") as f:
                    data = json.load(f)

                translates = data.get("translate", [])

                if not isinstance(translates, list):
                    continue

                file_count += 1

                for text in translates:
                    if not isinstance(text, str):
                        continue

                    string_count += 1

                    for ch in text:
                        char_set.add(ch)

            except Exception as e:
                raise RuntimeError(f"Failed to process {json_path}: {e}")

    return char_set