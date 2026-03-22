from PIL import ImageFont, Image, ImageDraw ,ImageEnhance
import json
import os

def change_brightness(image,factor=3):
    enhancer = ImageEnhance.Brightness(image)
    modfied_image =enhancer.enhance(factor)
    return modfied_image

def crop_and_save_image(image, x, y, sizex, sizey):
    try:
        crop_area = (x, y, x + sizex, y + sizey)
        cropped_image = image.crop(crop_area)
        return cropped_image
    except Exception as e:
        raise RuntimeError(f"Failed to crop image: {e}")

def is_chinese_char(char):
    # 判断字符汉字段内(不包括康熙部首字符)
    if char < '㐂' or char > '鶴':
        return False
    return True


def modify_nfh_data(nfh_data,offset,posX,posY,sizeX,sizeY, offsetX, offsetY):
    if posX < 0:
        posX = 0
    nfh_data[offset+0x04:offset+0x06] = posX.to_bytes(2, byteorder='big')
    nfh_data[offset+0x06:offset+0x08] = posY.to_bytes(2, byteorder='big')
    nfh_data[offset+0x14:offset+0x15] = sizeX.to_bytes(1, byteorder='big')
    nfh_data[offset+0x15:offset+0x16] = sizeY.to_bytes(1, byteorder='big')
    nfh_data[offset+0x08:offset+0x0A] = offsetX.to_bytes(2, byteorder='big') # b'\x00\x40' 64
    nfh_data[offset+0x0A:offset+0x0C] = offsetY.to_bytes(2, byteorder='big') # b'\x05\x80' 0x600  0x620 1568  0x580 1408 0x560 0x540 1344 0x500 1280



def build_font_task(progress, nfh_data = bytearray(),  fontdatas = {} , original_font_image = None, ttf_path = None, char_size = 25, replace_char_map = {}):
    try:
        progress("Building font image and NFH data...")
        result = build_font(nfh_data, fontdatas, original_font_image, ttf_path, char_size, replace_char_map)
    except Exception as e:
        raise RuntimeError(f"Failed to build font: {e}")
    
    return result


def build_font(nfh_data = bytearray(),  fontdatas = {} , original_font_image = None, ttf_path = None, char_size = 25, replace_char_map = {}):
    if len(nfh_data) == 0:
        raise ValueError("nfh_data cannot be empty")
    if len(fontdatas) == 0:
        raise ValueError("fontdatas cannot be empty")
    if original_font_image is None:
        raise ValueError("original_font_image cannot be None")
    if ttf_path is None:
        raise ValueError("ttf_path cannot be None")
    
    replace_image_path = os.path.join(os.path.dirname(ttf_path), "Pr.png")
    if not os.path.isfile(replace_image_path):
        raise FileNotFoundError(f"Replace 'Pr' image not found at path: {replace_image_path}")
    
    need_replace_char_set = set(replace_char_map.keys())
    
    font = ImageFont.truetype(ttf_path, char_size)
    fontColor = "white"
    
    nfh_offset = 0x450
    nfh_blocksize = 0x20
    
    new_font_offsetX = 0x40
    new_font_offsetY = 0x600
    
    cur_size = 24
    
    cur_nfh_offset = nfh_offset
    
    canvas_width = 2048
    canvas_height = 4096
    canvas = Image.new('RGBA', [2048, 4096], (0, 0, 0, 0))
    
    current_x = 0
    current_y = 0
    max_y_in_cur_row = 0
    
    kanacharID = []
    
    # 「㐂」 字开始为汉字段、之前的字符为符号字母、部首字、 平假名、片假名
    # 需要统计所有假名字母 >=ぁ, <=ヾ
    i = 0
    while i < len(fontdatas) and fontdatas[i]["char"] < "㐂":
        fontdata = fontdatas[i]
        fontposx = fontdata["x"]; fontposy = fontdata["y"]
        fontsizex = fontdata["sizex"] ; fontsizey = fontdata["sizey"]
        fontchar = fontdata["char"]
        if fontchar >= 'ぁ' and fontchar <= 'ヾ':
            kanacharID.append(i)
        else: 
            canvas.paste(crop_and_save_image(original_font_image,\
                fontposx, fontposy, fontsizex, fontsizey), (fontposx, fontposy))
        i = i+1    
        cur_nfh_offset += nfh_blocksize
    
    current_x = fontdatas[i]["x"]+1
    current_y = fontdatas[i]["y"]+1
    
    # 处理假名
    for kanaid in kanacharID:
        kanacharOffset = nfh_offset + kanaid * nfh_blocksize
        fontdata = fontdatas[kanaid]
        fontchar = fontdata["char"]
        draw = ImageDraw.Draw(canvas)
        
        if current_x + cur_size > canvas_width:
            current_x = 0
            current_y += max_y_in_cur_row
            current_y += 2
            max_y_in_cur_row = cur_size
        
        draw.text((current_x, current_y-3), fontchar, font=font, fill=fontColor)
        modify_nfh_data(nfh_data, kanacharOffset, current_x, current_y, cur_size+1, cur_size+1, new_font_offsetX, new_font_offsetY)
        
        current_x += cur_size 
        current_x +=2
        max_y_in_cur_row = max(max_y_in_cur_row, cur_size)
    
    # 扫描剩下的字符
    while i < len(fontdatas):
        fontdata = fontdatas[i]
        i = i+1
        fontchar = fontdata["char"]
        fontposx = fontdata["x"]; fontposy = fontdata["y"]
        fontsizex = fontdata["sizex"] ; fontsizey = fontdata["sizey"]
        fontoffsetx = fontdata["offsetx"]; fontoffsety = fontdata["offsety"]
        
        # 是要替换的汉字，直接用新字体绘制出来，更新nfh数据
        if fontchar in replace_char_map.keys():
            need_replace_char_set.remove(fontchar)
            drawchar = replace_char_map[fontchar]
            draw = ImageDraw.Draw(canvas)
            if current_x + cur_size > canvas_width:
                current_x = 0
                current_y += max_y_in_cur_row
                current_y += 2
                max_y_in_cur_row = cur_size

            draw.text((current_x, current_y-3), drawchar, font=font, fill=fontColor)
            modify_nfh_data(nfh_data, cur_nfh_offset, current_x, current_y, cur_size+1, cur_size+1, new_font_offsetX, new_font_offsetY)
            
            current_x += cur_size
            current_x +=2
            max_y_in_cur_row = max(max_y_in_cur_row, cur_size)   
                
        # 不用替换的字符，且原本有字模
        elif fontsizex >0 and fontsizey > 0:            
            # 是汉字，用新字体绘制，更新nfh数据
            if is_chinese_char(fontchar):
                drawchar = fontchar
                draw = ImageDraw.Draw(canvas)
                if current_x + cur_size > canvas_width:
                    current_x = 0
                    current_y += max_y_in_cur_row
                    current_y += 2
                    max_y_in_cur_row = cur_size
                if fontchar == '韈':    # Pr->韈 进行替换
                    font_image = Image.open(replace_image_path).convert("RGBA")
                    if font_image is None:
                        raise RuntimeError(f"Failed to load replace 'Pr' image from path: {replace_image_path}")
                    canvas.paste(font_image, (current_x, current_y-3), font_image)
                else:  
                    draw.text((current_x, current_y-3), drawchar, font=font, fill=fontColor)
                

                modify_nfh_data(nfh_data, cur_nfh_offset, current_x, current_y, cur_size+1, cur_size+1, new_font_offsetX, new_font_offsetY)
                
                current_x += cur_size 
                current_x +=2
                max_y_in_cur_row = max(max_y_in_cur_row, cur_size)
            # 不是汉字，直接复制
            else:
                if current_x + fontsizex > canvas_width:
                    current_x = 0
                    current_y += max_y_in_cur_row
                    current_y += 2
                    max_y_in_cur_row = fontsizey
                if fontchar in ('，','；','！','？'): 
                    draw.text((current_x, current_y-3), fontchar, font=font, fill=fontColor)
                    modify_nfh_data(nfh_data, cur_nfh_offset, current_x, current_y, cur_size+1, cur_size+1, new_font_offsetX, new_font_offsetY)
                    current_x += cur_size
                    current_x +=2
                    max_y_in_cur_row = max(max_y_in_cur_row, cur_size)
                
                else:
                    canvas.paste(crop_and_save_image(original_font_image, \
                        fontposx, fontposy, fontsizex, fontsizey), \
                        (current_x, current_y))
                    modify_nfh_data(nfh_data, cur_nfh_offset, current_x, current_y, fontsizex, fontsizey, fontoffsetx, fontoffsety)
                    current_x += fontsizex
                    current_x +=2
                    max_y_in_cur_row = max(max_y_in_cur_row, fontsizey)
        
        if current_y > canvas_height:
            raise RuntimeError(f"Canvas height is not enough to fit all characters.\nCharacter: {fontchar}, current_x: {current_x}, current_y: {current_y}")
        
        # 增加偏移量
        cur_nfh_offset += nfh_blocksize
        
    #print(len(need_replace_char_set))
    if len(need_replace_char_set) > 0:
        raise RuntimeError(f"Some characters in replace_char_map are not found in fontdatas. Characters: {need_replace_char_set}")
    
    return (nfh_data, canvas)