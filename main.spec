# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('mainwindow.ui', '.'),            # UI 文件放在同级目录
        ('resources/*', 'resources'),      # 整个 resources 目录
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,     # 如果你需要输出窗口改为 True
    disable_windowed_traceback=False,
    icon='favicon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='main'
)
