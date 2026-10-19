# 檔案名: config.py
# 修改行號區間: 1 - 182

import os  # 系統路徑
import shutil  # 備份檔案
import re  # 正則匹配
import sys  # 系統參數
import time  # 時間控制
import json  # JSON解析
import gzip  # Gzip壓縮
import zlib  # Zlib壓縮
import html  # HTML轉義
import pickle  # 物件序列
import ctypes  # C語言接口
import sqlite3  # SQL資料庫
import hashlib  # 哈希加密
import logging  # 日誌記錄
import requests  # 網路請求
import urllib.request  # 請求工具
import xml.etree.ElementTree as ET  # XML解析

from datetime import datetime, date  # 時間日期
from typing import List, Dict, Optional, Tuple  # 型別標註
from ctypes import c_char_p, c_void_p, c_int, c_double, byref, wintypes, pointer, sizeof, Structure  # C數據類型

#========================================================================================================

from PyQt6.QtCore import (  # 核心模組
    Qt,  # 核心常數
    QSize,  # 尺寸物件
    QObject,  # 基礎物件
    QEvent,  # 系統事件
    QTimer,  # 定時器
    QRectF,  # 浮點矩形
    QPoint,  # 座標點
    QPointF,  # 浮點座標
    QThread,  # 多執行緒
    pyqtSignal,  # 自訂信號
    QEasingCurve,  # 動畫曲線
    QCoreApplication,  # 核心應用
    QPropertyAnimation,  # 屬性動畫
    QAbstractNativeEventFilter,  # 原生過慮
)
#========================================================================================================
from PyQt6.QtGui import (  # 繪圖模組
    QPen,  # 畫筆
    QIcon,  # 圖示
    QFont,  # 字型
    QFontDatabase,  # 字型庫
    QColor,  # 顏色
    QRegion,  # 遮罩區域
    QAction,  # 選單動作
    QPixmap,  # 圖片
    QPalette,  # 調色盤
    QPainter,  # 繪圖工具
    QKeyEvent,  # 鍵盤事件
    QShortcut,  # 快捷鍵
    QDropEvent,  # 拖放事件
    QKeySequence,  # 按鍵組合
    QPainterPath,  # 繪圖路徑
    QGuiApplication,  # GUI應用
    QLinearGradient,  # 漸層顏色
)
#========================================================================================================
from PyQt6.QtWidgets import (  # 元件模組
    QMenu,  # 選單
    QFrame,  # 邊框外殼
    QDialog,  # 對話框
    QCheckBox,  # 勾選框
    QSizeGrip,  # 縮放手柄
    QFileDialog,  # 檔案選擇
    QMessageBox,  # 彈窗提示
    QMainWindow,  # 主視窗
    QPushButton,  # 按鈕
    QFormLayout,  # 表單佈局
    QSizePolicy,  # 尺寸策略
    QApplication,  # 應用程式
    QAbstractItemView,  # 列表視圖

    QGridLayout,  # 網格佈局
    QHBoxLayout,  # 水平佈局
    QVBoxLayout,  # 垂直佈局

    QLabel,  # 文字標籤
    QWidget,  # 基本元件
    QLineEdit,  # 單行輸入
    QListWidget,  # 項目列表
    QListWidgetItem,  # 項目物件

    QStyle,  # 樣式
    QSlider,  # 滑動條
    QSplitter,  # 分割容器
    QSplitterHandle,  # 分割手柄

    QScrollBar,  # 滾動條
    QScrollArea, # 滾動區域
    QProgressBar,  # 進度條
    
    QWidgetAction,  # 組件動作
    
    QKeySequenceEdit,  # 熱鍵編輯
)
#========================================================================================================

# 腳本目錄（支援 PyInstaller 打包後的執行檔路徑解析）
if getattr(sys, 'frozen', False):  # 打包判斷
    _script_dir = os.path.dirname(sys.executable)  # 執行檔檔目錄
else:  # 源碼執行
    _script_dir = os.path.dirname(os.path.abspath(__file__))  # 原始碼目錄
    
#========================================================================================================

# 應用程式版本（語意化版本：major.minor.patch）
APP_NAME = "K20 IPTV Player Pro"  # 程式名稱
APP_VERSION = "1.2.0"  # 目前版本

# 設定檔路徑
_SETTINGS_FILE = os.path.join(_script_dir, "k20_settings.json")  # 設定檔路徑

def get_resource_path(relative_path):  # 資源路徑
    """獲取資源檔的絕對路徑（支援 PyInstaller --onefile 臨時目錄）"""
    if hasattr(sys, '_MEIPASS'):  # 暫存目錄
        return os.path.join(sys._MEIPASS, relative_path)  # 傳回暫存
    return os.path.join(os.path.abspath("."), relative_path)  # 傳回絕對

# 讀取設定
def _load_settings():  # 讀取設定
    # 先讀主檔，壞了再試 .bak；壞檔改名保留，避免直接覆蓋
    for path in (_SETTINGS_FILE, _SETTINGS_FILE + ".bak"):  # 主檔 → 備份
        if not os.path.exists(path):  # 檔案不存在
            continue  # 試下一個
        try:  # 嘗試讀取
            with open(path, 'r', encoding='utf-8') as f:  # 開啟文字
                data = json.load(f)  # 解析JSON
            if isinstance(data, dict):  # 必須是字典
                return data  # 回傳設定
            raise ValueError("settings root is not a dict")  # 格式錯誤
        except Exception:  # 讀取/格式失敗
            if path == _SETTINGS_FILE:  # 只備份主檔
                try:  # 保留壞檔供救援
                    os.replace(path, f"{path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")  # 改名
                except OSError:  # 改名失敗
                    pass  # 忽略
    return {}  # 傳回預設

#========================================================================================================

# 儲存設定
def _save_settings(data):  # 保存設定
    tmp_file = _SETTINGS_FILE + ".tmp"  # 暫存檔
    try:  # 嘗試執行
        if os.path.exists(_SETTINGS_FILE):  # 先留一份備份
            try:  # 備份失敗不影響主流程
                shutil.copy2(_SETTINGS_FILE, _SETTINGS_FILE + ".bak")  # 複製舊設定
            except OSError:  # 無法備份
                pass  # 忽略
        with open(tmp_file, 'w', encoding='utf-8') as f:  # 寫暫存檔
            json.dump(data, f, ensure_ascii=False, indent=2)  # 寫入JSON
            f.flush()  # 沖刷緩衝
            os.fsync(f.fileno())  # 確保落盤
        os.replace(tmp_file, _SETTINGS_FILE)  # 原子替換，避免半截檔
    except Exception as e:  # 寫入失敗
        print(f"保存設置失敗: {e}")  # 印出失敗
        try:  # 清掉殘留暫存
            os.remove(tmp_file)  # 刪除
        except OSError:  # 不存在/被鎖
            pass  # 忽略


# 試加目錄
try:  # 嘗試執行
    # 新增目錄
    os.add_dll_directory(_script_dir)  # 加入DLL
# 載入失敗
except Exception:  # 補捉異常
    # 跳過
    pass  # 忽略錯誤

# 檢查路徑
if _script_dir not in os.environ.get("PATH", ""):  # 環境檢查
    # 補寫路徑
    os.environ["PATH"] = f"{_script_dir}{os.pathsep}{os.environ.get('PATH', '')}"  # 更新PATH

# 確保必要的快取與輸出資料夾自動建立
for _folder in ["epg_cache", "logo_cache", "snapshots"]:  # 巡迴資料夾
    _folder_path = os.path.join(_script_dir, _folder)  # 組合路徑
    os.makedirs(_folder_path, exist_ok=True)  # 自動建檔

# 確保預設設定檔存在
if not os.path.exists(_SETTINGS_FILE):  # 無設定檔
    _save_settings({  # 寫入預設
        "theme": "dark",  # 暗黑主題
        "volume": 100,  # 預設音量
        "last_channel": ""  # 上次頻道
    })  # 設定結束