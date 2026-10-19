# -*- mode: python ; coding: utf-8 -*-

import os  # 讀取環境變數

block_cipher = None

# 核心檔案：專案目錄、libs、K20_LIBS、D:\Libs 都可以
PROJECT_DIR = globals().get("SPECPATH") or os.getcwd()  # spec 所在目錄
CORE_FILES = ("libmpv-2.dll", "ffmpeg.exe", "yt-dlp.exe")  # 三大核心


def _core_dirs():  # 搜尋順序
    dirs = []  # 候選
    env_dir = os.environ.get("K20_LIBS", "").strip()  # 可選覆寫
    if env_dir:
        dirs.append(env_dir)
    dirs.append(PROJECT_DIR)  # 專案根目錄
    dirs.append(os.path.join(PROJECT_DIR, "libs"))  # 專案 libs
    dirs.append(r"D:\Libs")  # 舊習慣
    result, seen = [], set()  # 去重
    for d in dirs:
        d = os.path.abspath(d)
        key = os.path.normcase(d)
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result


def _find_core(name):  # 找單一檔案
    for d in _CORE_DIRS:
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return path
    return ""


_CORE_DIRS = _core_dirs()  # 搜尋目錄
_MISSING = [name for name in CORE_FILES if not _find_core(name)]  # 缺少的檔案
if _MISSING:
    raise SystemExit(
        "找不到核心檔案：" + "、".join(_MISSING)
        + "\n已搜尋：\n" + "\n".join(_CORE_DIRS)
        + "\n請放到專案根目錄、libs、或 D:\\Libs。"
    )

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],          # 保持空
    datas=[
        # PyInstaller 6 會放到 _internal，player_engine 用 sys._MEIPASS 查找
        *[(_find_core(name), '.') for name in CORE_FILES],
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