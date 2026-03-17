import json

def parse_nfh_task(progress, nfh_data = bytearray()):
    try:
        progress("Parsing NFH data...")
        result = parse_nfh2json(nfh_data)
    except Exception as e:
        raise RuntimeError(f"Failed to parse NFH data: {e}")
    
    return result


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
        offsetX = int.from_bytes(nfh_data[curOffset+0x8:curOffset+0x0A], byteorder='big')
        offsetY = int.from_bytes(nfh_data[curOffset+0xA:curOffset+0x0C], byteorder='big')
        
        res.append({"char":char, "x":posX, "y":posY, "sizex":sizeX, "sizey":sizeY, "offsetx":offsetX, "offsety":offsetY})
        curOffset += nfh_blocksize
    return res