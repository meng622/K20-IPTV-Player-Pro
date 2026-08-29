# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('libmpv-2.dll', '.'),  # 確保 libmpv 順利載入
        ('ffmpeg.exe', '.'),    # 📌 新增：打包 ffmpeg
        ('yt-dlp.exe', '.'),    # 📌 新增：打包 yt-dlp
    ],
    datas=[
        ('assets/icons', 'assets/icons'),  # 📌 新增：把本地 assets/icons 下所有 .svg 打包進去
    ],
    hiddenimports=['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    excludes=['PySide6'],  # 排除 PySide6 避免衝突
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
    a.binaries,  # 合併二進位檔
    a.zipfiles,  # 合併壓縮包
    a.datas,     # 合併資源
    [],
    name='K20_IPTV_Player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 無終端機視窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # 指定您的 .ico 圖示
)