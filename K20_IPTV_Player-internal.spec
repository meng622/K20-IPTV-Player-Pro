# -*- mode: python ; coding: utf-8 -*-

import os  # 讀取環境變數

block_cipher = None

# 共享庫目錄：可用 K20_LIBS 環境變數覆寫，預設仍是 D:\Libs
SHARED_LIBS = os.environ.get("K20_LIBS", r"D:\Libs")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],          # 保持空
    datas=[
        # PyInstaller 6 會放到 _internal，player_engine 已改用 sys._MEIPASS 查找
        (os.path.join(SHARED_LIBS, 'libmpv-2.dll'), '.'),
        (os.path.join(SHARED_LIBS, 'ffmpeg.exe'), '.'),
        (os.path.join(SHARED_LIBS, 'yt-dlp.exe'), '.'),
        ('assets/icons', 'assets/icons'),   # 若有資源目錄
    ],
    hiddenimports=['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    excludes=['PySide6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='K20_IPTV_Player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',   # 確保此檔案存在於專案目錄
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='K20_IPTV_Player',
)