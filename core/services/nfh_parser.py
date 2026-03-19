import json

def parse_nfh_task(progress, nfh_data = bytearray()):
    try:
        progress("Parsing NFH data...")
        result = parse_nfh2json(nfh_data)
    except Exception as e:
        raise RuntimeError(f"Failed to parse NFH data: {e}")
    
    return result

def modify_nfh_item(nfh_data , base_offset, key, new_value):
    if key == "char":
        encoded_value = new_value.encode("utf-16be")
        nfh_data[base_offset+0x16:base_offset+0x18] = encoded_value
    elif key == "x":
        nfh_data[base_offset+0x04:base_offset+0x06] = new_value.to_bytes(2, 'big')
    elif key == "y":
        nfh_data[base_offset+0x06:base_offset+0x08] = new_value.to_bytes(2, 'big')
    elif key == "sizex":
        nfh_data[base_offset+0x14:base_offset+0x15] = new_value.to_bytes(1, 'big')
    elif key == "sizey":
        nfh_data[base_offset+0x15:base_offset+0x16] = new_value.to_bytes(1, 'big')
    elif key == "offsetx":
        nfh_data[base_offset+0x8:base_offset+0x0A] = new_value.to_bytes(2, 'big')
    elif key == "offsety":
        nfh_data[base_offset+0xA:base_offset+0x0C] = new_value.to_bytes(2, 'big')
    elif key == "advancex":
        nfh_data[base_offset+0x0C:base_offset+0x0E] = new_value.to_bytes(2, 'big')
    elif key == "advancey":
        nfh_data[base_offset+0x0E:base_offset+0x10] = new_value.to_bytes(2, 'big', signed=True)
    elif key == "bboxX":
        nfh_data[base_offset+0x10:base_offset+0x12] = new_value.to_bytes(2, 'big')
    elif key == "bboxY":
        nfh_data[base_offset+0x12:base_offset+0x14] = new_value.to_bytes(2, 'big')


def parse_nfh2json(nfh_data = bytearray()):
    nfh_offset = 0x450
    nfh_blocksize = 0x20
    if len(nfh_data) <= nfh_offset+nfh_blocksize:
        raise ValueError("NFH data is invalid.")
    res = []
    curOffset = nfh_offset
    while(curOffset < len(nfh_data)):
        char = nfh_data[curOffset+0x16:curOffset+0x18].decode("utf-16be")
        posX = int.from_bytes(nfh_data[curOffset+0x04:curOffset+0x06], byteorder='big')
        posY = int.from_bytes(nfh_data[curOffset+0x06:curOffset+0x08], byteorder='big')
        sizeX = int.from_bytes(nfh_data[curOffset+0x14:curOffset+0x15], byteorder='big')
        sizeY = int.from_bytes(nfh_data[curOffset+0x15:curOffset+0x16], byteorder='big')
        
        advanceX = int.from_bytes(nfh_data[curOffset+0x0C:curOffset+0x0E], 'big')
        advanceY = int.from_bytes(nfh_data[curOffset+0x0E:curOffset+0x10], 'big', signed=True)
        
        bboxX = int.from_bytes(nfh_data[curOffset+0x10:curOffset+0x12], 'big')
        bboxY = int.from_bytes(nfh_data[curOffset+0x12:curOffset+0x14], 'big')
        
        offsetX = int.from_bytes(nfh_data[curOffset+0x8:curOffset+0x0A], byteorder='big')
        offsetY = int.from_bytes(nfh_data[curOffset+0xA:curOffset+0x0C], byteorder='big')
        
        res.append({
            "char":char, 
            "x":posX, 
            "y":posY, 
            "sizex":sizeX, 
            "sizey":sizeY, 
            "offsetx":offsetX, 
            "offsety":offsetY, 
            "advancex":advanceX,
            "advancey":advanceY,
            "blockOffset":curOffset
        })
        curOffset += nfh_blocksize
    return res