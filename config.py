import os  # 系統路徑
import re  # 正則匹配
import sys  # 系統參數
import time  # 時間控制
import json  # JSON解析
import ctypes  # C語言接口
import urllib.request  # 網絡請求
import sqlite3
import hashlib
import xml.etree.ElementTree as ET

from ctypes import c_char_p, c_void_p, c_int, c_double, byref  # C數據類型

#========================================================================================================

from PyQt6.QtCore import (
    Qt,  # 核心常數
    QSize,  # 尺寸對象
    QObject,
    QEvent,  # 系統事件
    QTimer,  # 定時器
    QRectF,  # 浮點矩形
    QPoint,  # 坐標點
    QPointF,  # 浮點坐標
    QThread,  # 多線程
    pyqtSignal,  # 自訂信號
)
#========================================================================================================
from PyQt6.QtGui import (
    QPen,  # 畫筆
    QIcon,
    QFont,  # 字體
    QFontDatabase,
    QColor,  # 顏色
    QRegion,  # 遮罩區域
    QAction,  # 菜單動作
    QPixmap,
    QPalette,
    QPainter,  # 繪圖工具
    QKeyEvent,  # 鍵盤事件
    QShortcut,  # 快捷鍵
    QKeySequence,  # 按鍵組合
    QPainterPath,  # 繪圖路徑
    QLinearGradient,  # 漸變顏色
)
#========================================================================================================
from PyQt6.QtWidgets import (
    QMenu,  # 選單
    QFrame,  # 邊框外殼
    QDialog,  # 對話框
    QCheckBox,  # 勾選框
    QFileDialog,  # 檔案選擇
    QMessageBox,  # 彈窗提示
    QMainWindow,  # 主視窗
    QPushButton,  # 按鈕
    QFormLayout,
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
    QListWidgetItem,  # 項目列表物件

    QStyle,
    QSlider,  # 滑動條
    QSplitter,  # 分割容器
    QSplitterHandle,  # 分割手柄

    QScrollBar,  # 滾動條
    QProgressBar,  # 進度條
)
#========================================================================================================

# 腳本目錄（支援 PyInstaller 打包後的執行檔路徑解析）
if getattr(sys, 'frozen', False):
    _script_dir = os.path.dirname(sys.executable)
else:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    
#========================================================================================================

# 設定檔路徑
_SETTINGS_FILE = os.path.join(_script_dir, "k20_settings.json")

def get_resource_path(relative_path):
    """獲取資源檔的絕對路徑（支援 PyInstaller --onefile 臨時目錄）"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# 讀取設定
def _load_settings():
    # 檔存在嗎
    if os.path.exists(_SETTINGS_FILE):
        # 試讀檔案
        try:
            # 開啟檔案
            with open(_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                # 轉為字典
                return json.load(f)
        # 讀取失敗
        except Exception:
            # 跳過
            pass
    # 回傳空字典
    return {}

#========================================================================================================

# 儲存設定
def _save_settings(data):
    # 試寫檔案
    try:
        # 開檔寫入
        with open(_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            # 轉檔寫入
            json.dump(data, f, ensure_ascii=False, indent=2)
    # 寫入失敗
    except Exception as e:
        # 印出錯誤
        print(f"保存設置失敗: {e}")


# 試加目錄
try:
    # 新增目錄
    os.add_dll_directory(_script_dir)
# 載入失敗
except Exception:
    # 跳過
    pass

# 檢查路徑
if _script_dir not in os.environ.get("PATH", ""):
    # 補寫路徑
    os.environ["PATH"] = f"{_script_dir}{os.pathsep}{os.environ.get('PATH', '')}"

# 確保必要的快取與輸出資料夾自動建立
for _folder in ["epg_cache", "logo_cache", "snapshots"]:
    _folder_path = os.path.join(_script_dir, _folder)
    os.makedirs(_folder_path, exist_ok=True)

# 確保預設設定檔存在
if not os.path.exists(_SETTINGS_FILE):
    _save_settings({
        "theme": "dark",
        "volume": 100,
        "last_channel": ""
    })
