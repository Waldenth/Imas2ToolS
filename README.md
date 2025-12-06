## Imas2ToolS

Tool set for idolm@ster2 ps3 ver translation.

![Preview](https://s2.loli.net/2025/12/06/BmdstciHgLz7Tfx.jpg)

### File Introduction in Imas2

- [ ] `mpc`:  The imas2 archive package file format.  include `xmb`, `tsk`, `scb` and `nut  `files
  - [x] preview
  - [x] unpack
  - [ ] repack 

- [ ] `scb`: The imas2 communicate script, include text which need to be translated (not in this tool now)
  - [x] modify text

- [ ] `xmb`: The imas2 system information file (mail, system info, picture position info,  etc.) can be repacked simply by overwriting the Japanese text at the corresponding offsets with the translated text, and filling the remaining unused bytes with zeros.
  - [ ] repack
  - [ ] replace

- [ ] `tsk`: The imas2 image and icon package file format. include `tsk` and `nut` files,  we can repack it by just rewrite offset data
  - [x] preview
  - [x] unpack
  - [ ] replace

- [ ] `nut`: The imas2 `DXT1`, `DXT3`, `DXT5` and `RAW`  `DDS` texture  package file format. (`DDS` size is same when the texture size is same, so we can also repack it by just rewrite offset data)
  - [x] preview
  - [x] unpack
  - [ ] replace
- [ ] `nfh`：The imas2 font image meta data, describe each kanji position, offset and size

### How to use

- python >= 3.7

```
pip install -r requirements.txt
python main.py
```