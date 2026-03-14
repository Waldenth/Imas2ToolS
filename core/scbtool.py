import sys
import pathlib
import os
import json
from core.scb_file_formats import scb 
from core import streamutility
import io

from core.scb_file_formats import scb
from core.scb_file_formats import msg
from core.scb_file_formats import scb0


temp_directory = "./temp"

def filter_null_chars(obj):
    if isinstance(obj, str):
        return obj.replace('\u0000', '') 
    elif isinstance(obj, list):
        return [filter_null_chars(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: filter_null_chars(value) for key, value in obj.items()}
    else:
        return obj
    
    

def exportJSON(script: scb.Scb, file: pathlib.Path, exportMap = {}, useDict = False, export_directory = ""):
    json_file = {"filename": file.name, "strings": []}

    for ds in script.msg_block.dialogue_strings_block.dialogue_strings:
        body = ""
        if useDict:
            for char in ds.body:
                if char in exportMap:
                    body += exportMap[char]
                else:
                    body += char
        else:
            body = ds.body
        json_file["strings"].append(body)

    file_directory = file.parent
    # 如果没有指定导出目录，默认使用原文件所在目录
    if export_directory == "":
        export_directory = file_directory


    json_file = filter_null_chars(json_file)

    json_output_path = pathlib.Path(export_directory) / f"{file.stem}.json"
    
    with open(json_output_path, "w", encoding="utf-16") as f:
        json.dump(json_file, f, ensure_ascii=False, indent=1)

    return json_output_path


def importJSON(file: pathlib.Path, ImportMap = {}, useDict = False) -> json:
    json_file_path = file.parent / f'{file.name}'
    with open(json_file_path, 'r', encoding='utf-16') as f:
        original_data = f.read()
        converted_data = ""
        if useDict:
            for char in original_data:
                if char in ImportMap:
                    converted_data += ImportMap[char]
                else:
                    converted_data += char
        else:
            converted_data = original_data 
        
        data = json.loads(converted_data)
    filename = data.get("filename", "")
    # 翻译translate 为 制作scb的strings列表
    translate = data.get("translate", [])
    # 如果没有 translate 字段，则使用原来的 strings 字段
    if not translate:
        translate = data.get("strings", [])
    
    f.close()

    return {
        "filename": filename,
        "strings": translate
    }


def extractSCB(filename, old_script: scb.Scb):
    global temp_directory
    if not os.path.exists(temp_directory):
        os.makedirs(temp_directory)
        
    scb0_file_path = temp_directory + '/'+  f'{filename}.scb0'
    new_scb0 = open(scb0_file_path, "+wb")
    new_scb0.write(old_script.header_cache.files[0].file)
    new_scb0.flush()
    return new_scb0

def injectTranslation(new_SCB0, translated_dialogue_json):
    newMSGBlock = msg.constructMSGBlock(new_SCB0, translated_dialogue_json)
    new_SCB0_file_path =  f'{new_SCB0.name}.translated'
    new_script = open(new_SCB0_file_path, "+wb")
    file_SCB0 = scb0.Scb0.from_file(new_SCB0.name)
    new_script.write(file_SCB0.header)
    
    # Write header of sections for new SCB file
    new_section_offset = 0
    for section in file_SCB0.sections:

        label = section.label
        len_section = section.len_section

        if new_section_offset == 0:
            new_section_offset = section.ofs_section
        if section.label[0:3] == 'MSG':
            len_section = len(newMSGBlock.getvalue()) # gets length of new MSG block

        streamutility.writeStrToLong(new_script, label)
        streamutility.writePadding(new_script, 4, streamutility.Padding.post_MSG_padding)
        streamutility.writeHexToLong(new_script, len_section)
        streamutility.writeHexToLong(new_script, new_section_offset)
        streamutility.writePadding(new_script, 16, streamutility.Padding.post_MSG_padding)
        new_section_offset += len_section

    # Write section data
    for section in file_SCB0.sections:
        block = section.block
        if section.label[0:3] == 'MSG':
            block = newMSGBlock.getvalue()
        new_script.write(block)

    new_script.flush()

    return new_script

def writeSCB(filename, old_script: scb.Scb, new_SCB0, export_directory):

    new_script_path = pathlib.Path(export_directory) / f'{filename}.scb'
    new_script = open(new_script_path, "+wb")
    
    # writeIV(new_script)
    writePAC(old_script, new_script, new_SCB0)

def writeIV(new_script):
    # initialization_vector = old_script.initialization_vector
    # new_script.write(initialization_vector)
    blank_iv = bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    new_script.write(blank_iv)

def writePAC(old_script: scb.Scb, new_script: io.BufferedRandom, new_SCB0: io.BufferedRandom):
    # PAC Header
    new_script.write(old_script.header_cache.header)
    streamutility.writeHexToLong(new_script, old_script.header_cache.num_files)
    new_script.write(old_script.header_cache.header_cache_padding)
    streamutility.writeHexToLong(new_script, old_script.header_cache.ofs_entry)
    streamutility.writeHexToLong(new_script, old_script.header_cache.ofs_msg)
    streamutility.writeHexToLong(new_script, old_script.header_cache.ofs_file)
    new_script.write(old_script.header_cache.header_cache_padding_2)

    new_file_offset = 0
    for i in range(0, len(old_script.header_cache.files)):
        file: scb.Scb.PacFile
        file = old_script.header_cache.files[i]
        file_length = file.len_file
        
        
        new_script.write(file.filesize_padding)
        if i == 0: # SCB file length, from new SCB0
            file_length = new_SCB0.tell()
        streamutility.writeHexToLong(new_script, file_length)
        streamutility.writeHexToLong(new_script, new_file_offset)
        streamutility.writeHexToLong(new_script, file.fn_index)
        streamutility.writeHexToLong(new_script, file.fp_index)
        new_script.write(file.file_meta_padding)

        new_file_offset += file_length

    # PAC files
    new_SCB0.seek(0)
    new_script.write(new_SCB0.read())
    new_script.write(old_script.scb_padding)

def createSCB(jsonfile: pathlib.Path, ImportMap = {}, useDict = False, export_directory = ""):
    file_directory = jsonfile.parent
    # 如果没有指定导出目录，默认使用原文件所在目录
    if export_directory == "":
        export_directory = file_directory

    translated_dialogue_json = importJSON(jsonfile, ImportMap, useDict)
    
    old_script = scb.Scb.from_file(jsonfile.parent / f'{jsonfile.stem}.scb')
    new_SCB0 = extractSCB(jsonfile.stem, old_script)
    newSCB0translated = injectTranslation(new_SCB0, translated_dialogue_json)
    writeSCB(jsonfile.stem, old_script, newSCB0translated, export_directory)
    return pathlib.Path(export_directory) / f'{jsonfile.stem}.scb'