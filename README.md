## Imas2ToolS

Tool set for idolm@ster2 ps3 ver. chinese translation group.

![Preview_1](https://picui.ogmua.cn/s1/2026/03/20/69bd583053b7e.webp)

![Preview_2](https://picui.ogmua.cn/s1/2026/03/20/69bd58301e4ca.webp)


### File Introduction in Imas2

- [ ] `mpc`:  The imas2 archive package file format, include `xmb`, `tsk`, `scb` and `nut`files
  - [x] preview
  - [x] unpack
  - [x] repack 

- [ ] `scb`: The imas2 communicate script, include text which need to be translated
  - [x] modify text
  
- [ ] `xmb`: The imas2 system information file (mail, system info, picture position info,  etc.) can be repacked simply by overwriting the Japanese text at the corresponding offsets with the translated text, and filling the remaining unused bytes with zeros.
  - [x] preview xml
  - [x] export text json
  - [x] rewrite
  - [x] replace
  - [ ] rebuild
    ![preiview_xmb](https://picui.ogmua.cn/s1/2026/03/20/69bd62aec4222.webp)

- [ ] `tsk`: The imas2 image and icon package file format. include `tsk` and `nut` files,  we can repack it by just rewrite offset data
  - [x] preview
  - [x] unpack
  - [x] replace
  - [ ] repack

- [ ] `nut`: The imas2 `DXT1`, `DXT3`, `DXT5` and `RAW`  `DDS` texture  package file format. (`DDS` size is same when the texture size is same, so we can also repack it by just rewrite offset data)
  - [x] preview
  - [x] unpack
  - [x] replace
  - [ ] repack

- [ ] `nfh`: The imas2 font image meta data, describe each kanji position, offset and size
  - [x] preview and render font text
  - [x] modify item 
  - [x] rewrite and generate Hanzi remap dictionary
  - [ ] rebuild

- [ ] `dds`: Image format used primarily to store, compress, and render 3D textures in video games and real-time simulations
  - [x] Convert (Windows)
    ![Tools](https://picui.ogmua.cn/s1/2026/03/20/69bd61d6c6adb.webp)
### How to use

- python >= 3.7

```
pip install -r requirements.txt
python main.py
```