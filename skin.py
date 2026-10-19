# skin.py
from config import *  # 載入設定
from PyQt6.QtSvg import QSvgRenderer  # 載入圖套

# Windows 毛玻璃結構
class ACCENT_POLICY(Structure):  # 模糊結構
    _fields_ = [  # 結構欄位
        ("AccentState", c_int),  # 模糊狀態
        ("AccentFlags", c_int),  # 模糊標記
        ("GradientColor", c_int),  # 漸變色彩
        ("AnimationId", c_int)  # 動畫識別
    ]  # 欄位結尾

class WINDOWCOMPOSITIONATTRIBDATA(Structure):  # 屬性結構
    _fields_ = [  # 結構欄位
        ("Attribute", c_int),  # 屬性標記
        ("Data", c_void_p),  # 數據指針
        ("SizeOfData", c_int)  # 數據大小
    ]  # 欄位結尾

class WindowBlurManager:  # 模糊管理器
    """呼叫 Windows Native API 為視窗套用 Acrylic 高斯模糊"""  # 功能說明
    @staticmethod  # 靜態方法
    def enable_acrylic(hwnd: int, bg_color_hex="#141423", alpha=180):  # 開毛玻璃
        if sys.platform != "win32":  # 非微軟系統
            return  # 直接跳出
        
        try:  # 嘗試調用
            bg_color_hex = bg_color_hex.lstrip('#')  # 除去井號
            r = int(bg_color_hex[0:2], 16)  # 解析紅光
            g = int(bg_color_hex[2:4], 16)  # 解析綠光
            b = int(bg_color_hex[4:6], 16)  # 解析藍光
            abgr_color = (alpha << 24) | (b << 16) | (g << 8) | r  # 算色顏碼

            user32 = ctypes.windll.user32  # 載系統函
            accent = ACCENT_POLICY()  # 建模糊檔
            accent.AccentState = 4  # 設丙烯態
            accent.GradientColor = abgr_color  # 設底色值

            data = WINDOWCOMPOSITIONATTRIBDATA()  # 建數據檔
            data.Attribute = 19  # 設屬性碼
            data.Data = ctypes.cast(pointer(accent), c_void_p)  # 轉數據針
            data.SizeOfData = sizeof(accent)  # 設數據長

            user32.SetWindowCompositionAttribute(hwnd, pointer(data))  # 傳系統套
        except Exception as e:  # 捕捉例外
            print(f"[WindowBlurManager] Failed to apply acrylic effect: {e}")  # 印報錯訊


class SkinManager:  # 外觀管理器
    def __init__(self, main_window):  # 初始化器
        self.win = main_window  # 綁主視窗

    def get_skin_stylesheet(self, theme="purple"):  # 產皮樣式
        # 色彩代碼
        themes = {  # 主題清單
            "purple": {  # 紫色主題
                "bg_dark_hex": "#0d0614",  # 暗底顏碼
                "bg_main": "rgba(13, 6, 20, 0.85)",  # 主底色值
                "bg_panel": "rgba(22, 10, 35, 0.80)",  # 面板色值
                "glass_border": "rgba(255, 255, 255, 0.28)",  # 玻璃邊色
                "accent": "#8529ff",  # 強調色值
                "border": "#5700c9",  # 邊框色值
                "gradient": ("#5700c9", "#6e16e5", "#8529ff")  # 漸變色組
            },  # 紫色結尾
            "cyan": {  # 青色主題
                "bg_dark_hex": "#06111e",  # 暗底顏碼
                "bg_main": "rgba(6, 17, 30, 0.85)",  # 主底色值
                "bg_panel": "rgba(10, 28, 48, 0.80)",  # 面板色值
                "glass_border": "rgba(255, 255, 255, 0.28)",  # 玻璃邊色
                "accent": "#38bdf8",  # 強調色值
                "border": "#0284c7",  # 邊框色值
                "gradient": ("#0284c7", "#06b6d4", "#38bdf8")  # 漸變色組
            },  # 青色結尾
            "emerald": {  # 綠主題色
                "bg_dark_hex": "#03140e",  # 暗底顏碼
                "bg_main": "rgba(3, 20, 14, 0.85)",  # 主底色值
                "bg_panel": "rgba(7, 38, 26, 0.80)",  # 面板色值
                "glass_border": "rgba(255, 255, 255, 0.28)",  # 玻璃邊色
                "accent": "#34d399",  # 強調色值
                "border": "#059669",  # 邊框色值
                "gradient": ("#059669", "#10b981", "#34d399")  # 漸變色組
            },  # 綠色結尾
            "slate": {  # 灰主題色
                "bg_dark_hex": "#0f131a",  # 暗底顏碼
                "bg_main": "rgba(15, 19, 26, 0.85)",  # 主底色值
                "bg_panel": "rgba(24, 30, 40, 0.80)",  # 面板色值
                "glass_border": "rgba(255, 255, 255, 0.28)",  # 玻璃邊色
                "accent": "#94a3b8",  # 強調色值
                "border": "#475569",  # 邊框色值
                "gradient": ("#475569", "#64748b", "#94a3b8")  # 漸變色組
            }  # 灰色結尾
        }  # 字典結尾
        c = themes.get(theme, themes["purple"])  # 拿當前色檔
        self.win.current_theme_accent = c["accent"]  # 存強色值
        self.win.current_theme_config = c  # 存主題設定

        return f"""
            /* ==================================================
               📌 區塊 0：全局字型重置 (防止退回系統宋體)
               ================================================== */
            * {{
                font-family: "Microsoft JhengHei", "Segoe UI", "PingFang TC", "Helvetica Neue", Arial, sans-serif !important;
            }}

            QWidget, QLabel, QPushButton, QLineEdit, QComboBox, QListWidget, QTreeWidget {{
                font-family: "Microsoft JhengHei", "Segoe UI", "PingFang TC", Arial, sans-serif !important;
            }}
        
            /* ==================================================
               📌 區塊 1：視窗主體與基本面板 (iOS 毛玻璃透明化)
               ================================================== */
            QMainWindow, QDialog {{ 
                background: {c['bg_main']} !important; 
            }}
            
            /* 🎯 側邊欄整體背景與右側玻璃分隔線 */
            QWidget#sidebar {{
                background: {c['bg_panel']} !important;
                border-right: 1px solid rgba(255, 255, 255, 0.12) !important;
            }}
            
            /* 🎯 側邊欄按鈕：平時完全透明扁平 */
            QWidget#sidebar QPushButton {{
                background: transparent !important;
                border: none !important;
                border-radius: 10px !important;
                min-height: 36px;
                padding: 6px 0;
                margin: 2px 4px;
            }}
            
            /* 🎯 側邊欄按鈕：鼠標懸停時才顯現玻璃輪廓 (調淺亮色) */
            QWidget#sidebar QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.14), stop:1 rgba(255, 255, 255, 0.04)) !important;
                border: 1px solid rgba(255, 255, 255, 0.20) !important;
                border-top: 1px solid rgba(255, 255, 255, 0.45) !important;
            }}
            
            /* 🎯 側邊欄按鈕：選中時柔和主題玻璃色 */
            QWidget#sidebar QPushButton[active="true"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.22), stop:1 rgba(255, 255, 255, 0.08)) !important;
                border: 1px solid {c['accent']} !important;
                border-top: 1px solid rgba(255, 255, 255, 0.65) !important;
            }}

            /* 🎯 右上角 [節目表] 按鈕：平時扁平，懸停才顯現淡亮玻璃 */
            QWidget#top_bar QPushButton {{
                background: transparent !important;
                border: none !important;
                border-radius: 10px !important;
                color: #ffffff !important;
                padding: 4px 10px !important;
            }}
            QWidget#top_bar QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.14), stop:1 rgba(255, 255, 255, 0.04)) !important;
                border: 1px solid rgba(255, 255, 255, 0.20) !important;
                border-top: 1px solid rgba(255, 255, 255, 0.45) !important;
            }}

            QWidget#sidebar QLabel#sidebar_logo,
            QWidget#sidebar QPushButton#sidebar_logo,
            QWidget#sidebar QPushButton#sidebar_logo:hover,
            QWidget#sidebar QPushButton#sidebar_logo:pressed {{
                background: transparent !important;
                background-color: transparent !important;
                border: none !important;
                color: {c['accent']} !important;
                font-size: 18px !important;
                font-weight: bold !important;
                padding: 10px 0 !important;
            }}

            /* ==================================================
               📌 區塊 2：輸入框 (QLineEdit)
               ================================================== */
            /* 🎯 紅色框：搜尋輸入框玻璃質感 */
            QLineEdit {{
                background: rgba(0, 0, 0, 0.25) !important; 
                border: 1px solid rgba(255, 255, 255, 0.15) !important; 
                border-top: 1px solid rgba(255, 255, 255, 0.35) !important; 
                border-radius: 10px !important; 
                padding: 6px 12px; 
                color: #ffffff; 
            }}
            QLineEdit:focus {{ 
                border: 1px solid {c['accent']} !important; 
                background: rgba(0, 0, 0, 0.40) !important; 
            }}

            /* ==================================================
               📌 區塊 3：主介面頻道列表 & 最近播放
               ================================================== */
            QListWidget {{
                background: transparent !important; 
                border: none !important; 
                outline: none !important; 
                selection-background-color: transparent !important;
                selection-color: #ffffff !important;
            }}
            
            QListWidget::item {{
                /* 🎯 1. iOS 上亮下暗光感漸變 */
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.14), stop:1 rgba(255, 255, 255, 0.03)) !important; 
                /* 🎯 2. iOS 邊框立體反射：頂邊極亮，底邊極淡 */
                border: 1px solid rgba(255, 255, 255, 0.15) !important; 
                border-top: 1px solid rgba(255, 255, 255, 0.40) !important; 
                /* 🎯 3. 大弧度 iOS 圓角 */
                border-radius: 14px !important; 
                margin-bottom: 8px; 
                margin-right: 10px;
                padding: 8px 12px; 
                color: #ffffff !important; 
            }}
            
            QListWidget QLabel,
            QListWidget::item QLabel,
            QListWidget::item:selected QLabel,
            QListWidget::item:hover QLabel {{
                color: #ffffff !important;
                background: transparent !important;
            }}
            
            QListWidget::item:hover {{ 
                /* 🎯 Hover 時光亮增強 */
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.25), stop:1 rgba(255, 255, 255, 0.08)) !important;
                border: 1px solid {c['accent']} !important; 
                border-top: 1px solid rgba(255, 255, 255, 0.65) !important;
                color: #ffffff !important; 
            }}
            
            QListWidget::item:selected,
            QListWidget::item:selected:active,
            QListWidget::item:selected:hover {{
                /* 🎯 選中時透光主題色漸變 */
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['accent']}, stop:1 {c['border']}) !important; 
                border: 1px solid rgba(255, 255, 255, 0.5) !important; 
                border-top: 1px solid rgba(255, 255, 255, 0.8) !important;
                color: #ffffff !important; 
                font-weight: bold; 
            }}

            /* ==================================================
               📌 區塊 4：右鍵選單與播放按鈕 (QMenu / QPushButton)
               ================================================== */
            QMenu {{ 
                background: {c['bg_panel']} !important; 
                border: 1px solid {c['glass_border']} !important; 
                border-radius: 12px !important; 
                color: #ffffff; 
                padding: 4px; 
            }}
            QMenu::item {{ 
                padding: 6px 16px; 
                border-radius: 6px;
                background: transparent;
                color: #e2e8f0;
            }}
            /* 🎯 讓預設排序 (QMenu) 完全對齊全部分組的標準 Accent 高亮質感 */
            QMenu::item:selected {{ 
                background: {c['accent']} !important; 
                color: #ffffff !important; 
                font-weight: bold;
            }}
            QMenu::item:pressed {{
                background: {c['accent']} !important;
            }}
            
            /* 🎯 分組下拉選單（Hover 與 Selected 完全統一為當前主題 Accent 色） */
            QListWidget#group_menu_list {{
                background: transparent !important;
                border: none !important;
                outline: none !important;
                padding: 2px !important;
            }}
            QListWidget#group_menu_list::item {{
                background: transparent !important;
                border: none !important;
                border-radius: 6px !important;
                margin: 1px 0px !important;
                padding: 4px 10px !important;
                color: #e2e8f0 !important;
            }}
            QListWidget#group_menu_list::item:hover {{
                background: {c['accent']} !important; /* 🎯 滑鼠移過即刻亮起主題 Accent 色 */
                border: none !important;
                color: #ffffff !important;
                font-weight: bold !important;
            }}
            QListWidget#group_menu_list::item:selected {{
                background: {c['accent']} !important; /* 🎯 選中狀態保持一致 */
                border: none !important;
                color: #ffffff !important;
                font-weight: bold !important;
            }}

            /* ==================================================
               📌 區塊 5：子視窗通用按鈕與清單規管 (QDialog UI)
               ================================================== */
            QDialog QPushButton {{
                background: {c['bg_panel']};
                border: 1px solid {c['glass_border']};
                color: #ccc;
                border-radius: 8px;
                padding: 8px;
            }}
            QDialog QPushButton:hover {{
                border: 1px solid {c['accent']};
                color: #ffffff;
            }}
            QDialog QPushButton#primary_btn, QDialog QPushButton[primary="true"] {{
                background: {c['accent']} !important;
                color: #ffffff !important;
                border: none;
            }}

            /* ==================================================
               📌 區塊 6：M3U 管理器自定義卡片
               ================================================== */
            QDialog QListWidget {{
                selection-background-color: transparent !important;
                selection-color: transparent !important;
            }}
            QDialog QListWidget::item,
            QDialog QListWidget::item:selected,
            QDialog QListWidget::item:selected:active,
            QDialog QListWidget::item:selected:hover,
            QDialog QListWidget::item:hover {{
                background: transparent !important;
                background-color: transparent !important;
                border: none !important;
                outline: none !important;
                color: transparent !important;
            }}

            QFrame#m3u_item_frame {{
                background-color: {c['bg_panel']} !important;
                border: 1px solid {c['glass_border']};
                border-radius: 10px;
            }}
            QFrame#m3u_item_frame:hover {{
                border: 1px solid {c['accent']};
            }}
            QFrame#m3u_item_frame[active="true"] {{
                border: 1.5px solid #ffffff !important;
                background-color: {c['accent']} !important; 
            }}

            QLabel#m3u_item_title {{
                color: #ffffff !important;
                font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
                font-weight: bold;
                font-size: 13px;
                background: transparent !important;
                border: none !important;
            }}
            QLabel#m3u_item_url {{
                color: #cbd5e1 !important;
                font-size: 11px;
                background: transparent !important;
                border: none !important;
            }}
            QFrame#m3u_item_frame[active="true"] QLabel#m3u_item_url {{
                color: #ffffff !important;
            }}

            QLabel#m3u_item_badge {{
                color: #ffffff !important;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 4px;
                border: none !important;
            }}
            QLabel#m3u_item_badge[type="local"] {{
                background-color: #0284c7 !important;
            }}
            QLabel#m3u_item_badge[type="url"] {{
                background-color: {c['accent']} !important;
            }}
            QLabel#m3u_item_star {{
                background: transparent !important;
                border: none !important;
                font-size: 12px;
            }}

            /* ==================================================
               📌 區塊 7：全域極簡滾動條美化 (ScrollBars)
               ================================================== */
            /* 🎯 垂直滾動條 */
            QAbstractScrollArea QScrollBar:vertical, QListWidget QScrollBar:vertical, QDialog QScrollBar:vertical {{ 
                border: none !important; 
                background: rgba(0, 0, 0, 0.2) !important; 
                width: 6px !important; 
                margin: 0px !important; 
            }}
            QAbstractScrollArea QScrollBar::handle:vertical, QListWidget QScrollBar::handle:vertical, QDialog QScrollBar::handle:vertical {{ 
                background: {c['border']} !important; 
                min-height: 20px !important; 
                border-radius: 3px !important; 
            }}
            QAbstractScrollArea QScrollBar::handle:vertical:hover, QListWidget QScrollBar::handle:vertical:hover, QDialog QScrollBar::handle:vertical:hover {{ 
                background: {c['accent']} !important; 
            }}
            QAbstractScrollArea QScrollBar::add-line:vertical, QAbstractScrollArea QScrollBar::sub-line:vertical,
            QListWidget QScrollBar::add-line:vertical, QListWidget QScrollBar::sub-line:vertical,
            QDialog QScrollBar::add-line:vertical, QDialog QScrollBar::sub-line:vertical {{ 
                height: 0px !important; 
                background: none !important; 
            }}
            QAbstractScrollArea QScrollBar::add-page:vertical, QAbstractScrollArea QScrollBar::sub-page:vertical,
            QListWidget QScrollBar::add-page:vertical, QListWidget QScrollBar::sub-page:vertical,
            QDialog QScrollBar::add-page:vertical, QDialog QScrollBar::sub-page:vertical {{ 
                background: none !important; 
            }}

            /* 🎯 水平滾動條（統一主題藍色） */
            QAbstractScrollArea QScrollBar:horizontal, QListWidget QScrollBar:horizontal, QDialog QScrollBar:horizontal {{ 
                border: none !important; 
                background: rgba(0, 0, 0, 0.2) !important; 
                height: 6px !important; 
                margin: 0px !important; 
            }}
            QAbstractScrollArea QScrollBar::handle:horizontal, QListWidget QScrollBar::handle:horizontal, QDialog QScrollBar:horizontal {{ 
                background: {c['accent']} !important; 
                min-width: 20px !important; 
                border-radius: 3px !important; 
            }}
            QAbstractScrollArea QScrollBar::handle:horizontal:hover, QListWidget QScrollBar::handle:horizontal:hover, QDialog QScrollBar::handle:horizontal:hover {{ 
                background: {c['accent']} !important; 
            }}
            QAbstractScrollArea QScrollBar::add-line:horizontal, QAbstractScrollArea QScrollBar::sub-line:horizontal,
            QListWidget QScrollBar::add-line:horizontal, QListWidget QScrollBar::sub-line:horizontal,
            QDialog QScrollBar::add-line:horizontal, QDialog QScrollBar::sub-line:horizontal {{ 
                height: 0px !important; 
                background: none !important; 
            }}
            QAbstractScrollArea QScrollBar::add-page:horizontal, QAbstractScrollArea QScrollBar::sub-page:horizontal,
            QListWidget QScrollBar::add-page:horizontal, QListWidget QScrollBar::sub-page:horizontal,
            QDialog QScrollBar::add-page:horizontal, QDialog QScrollBar::sub-page:horizontal {{ 
                background: none !important; 
            }}
            
            

            QDialog QScrollBar:horizontal {{
                border: none !important;
                background: rgba(0, 0, 0, 0.2) !important;
                height: 8px !important;
                border-radius: 4px !important;
            }}
            QDialog QScrollBar::handle:horizontal {{
                background: {c['border']} !important;
                min-width: 20px !important;
                border-radius: 4px !important;
            }}
            QDialog QScrollBar::handle:horizontal:hover {{
                background: {c['accent']} !important;
            }}
            QDialog QScrollBar::add-line:horizontal, QDialog QScrollBar::sub-line:horizontal {{
                width: 0px !important;
                background: none !important;
            }}
            QDialog QScrollBar::add-page:horizontal, QDialog QScrollBar::sub-page:horizontal {{
                background: none !important;
            }}
            
            /* ==================================================
               📌 區塊 8：頻道面板專屬元件樣式
               ================================================== */
            QWidget#bottom_bar, #bottom_bar {{
                background: {c['bg_panel']} !important; 
                border: 1px solid rgba(255, 255, 255, 0.12) !important; 
                border-top: 1px solid rgba(255, 255, 255, 0.35) !important; 
                border-radius: 16px !important;  /* 🎯 控制欄大底盤弧度 */
            }}

            QWidget#bottom_bar QPushButton, #bottom_bar QPushButton,
            QPushButton[role="filter_btn"], QPushButton[role="menu_btn"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.14), stop:1 rgba(255, 255, 255, 0.03)) !important;
                border: 1px solid rgba(255, 255, 255, 0.15) !important;
                border-top: 1px solid rgba(255, 255, 255, 0.40) !important;
                border-radius: 12px !important;  /* 🎯 控制按鈕弧度 */
                color: #ffffff !important;
                padding: 4px 10px !important;
                font-size: 12px !important;
                min-height: 22px;
            }}

            QWidget#bottom_bar QPushButton:hover, #bottom_bar QPushButton:hover,
            QPushButton[role="filter_btn"]:hover, QPushButton[role="menu_btn"]:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.28), stop:1 rgba(255, 255, 255, 0.10)) !important;
                border: 1px solid {c['accent']} !important;
                border-top: 1px solid rgba(255, 255, 255, 0.70) !important;
            }}

            /* 🎯 紅色框：全部分組、預設排序、測速按鈕及 4K/FHD 畫質按鈕 */
            QWidget#channel_panel QPushButton,
            QPushButton[role="filter_btn"], 
            QPushButton[role="menu_btn"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.12), stop:1 rgba(255, 255, 255, 0.03)) !important;
                border: 1px solid rgba(255, 255, 255, 0.15) !important;
                border-top: 1px solid rgba(255, 255, 255, 0.40) !important;
                border-radius: 12px !important; 
                color: #ffffff !important;
                padding: 4px 10px !important;
                font-size: 12px !important;
            }}

            QWidget#channel_panel QPushButton:hover,
            QPushButton[role="filter_btn"]:hover, 
            QPushButton[role="menu_btn"]:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.22), stop:1 rgba(255, 255, 255, 0.08)) !important;
                border: 1px solid {c['accent']} !important;
                border-top: 1px solid rgba(255, 255, 255, 0.65) !important;
            }}

            QLabel[role="channel_label"] {{
                color: #ffffff !important; 
                font-size: 13px; 
                border: none !important; 
                background: transparent !important;
            }}
            QPushButton[role="star_btn"] {{
                font-size: 16px; 
                border: none; 
                background: transparent;
            }}
            QPushButton[role="star_btn"][favorited="true"] {{
                color: #f59e0b;
            }}
            QPushButton[role="star_btn"][favorited="false"] {{
                color: #555566;
            }}
            QPushButton[role="del_btn"] {{
                color: #ff4d4d; 
                font-size: 14px; 
                border: none; 
                background: transparent;
            }}
            
            /* ==================================================
               📌 區塊 9：全域進度條樣式
               ================================================== */
            QProgressBar {{
                background-color: rgba(0, 0, 0, 0.4);
                color: #ffffff;
                border: 1px solid {c['glass_border']};
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {c['accent']};
                border-radius: 3px;
            }}
            
            /* ==================================================
               📌 區塊 10：系統設置對話框專屬樣式
               ================================================== */
            QDialog QLabel {{ 
                color: #e2e8f0; 
            }}
            QDialog QLabel#settings_title {{
                font-size: 18px; 
                font-weight: bold; 
                color: #f8fafc;
            }}
            QDialog QCheckBox {{ 
                color: #cbd5e1; 
                font-size: 13px; 
                spacing: 8px; 
            }}
            QDialog QCheckBox::indicator {{ 
                width: 18px; 
                height: 18px; 
                border-radius: 4px; 
                border: 1px solid {c['glass_border']}; 
                background-color: {c['bg_panel']}; 
            }}
            QDialog QCheckBox::indicator:checked {{ 
                background-color: {c['accent']}; 
                border-color: {c['accent']}; 
            }}
            QDialog QPushButton#btn_save {{ 
                background-color: {c['accent']}; 
                color: white; 
                border: none; 
                border-radius: 6px; 
                font-weight: bold; 
                padding: 6px 16px; 
            }}
            QDialog QPushButton#btn_save:hover {{ 
                background-color: {c['accent']}; 
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}
            QDialog QPushButton#btn_cancel {{ 
                background-color: {c['bg_panel']}; 
                color: #94a3b8; 
                border: 1px solid {c['glass_border']}; 
                border-radius: 6px; 
                padding: 6px 16px; 
            }}
            QDialog QPushButton#btn_cancel:hover {{ 
                background-color: {c['border']}; 
                color: white; 
            }}
            
            /* ==================================================
               📌 區塊 11：三線 Menu 按鈕與側邊欄 Hover 色彩
               ================================================== */
            
            /* 🎯 頂部欄整體背景與底部玻璃分隔線 */
            QWidget#top_bar {{
                background: {c['bg_panel']} !important;
                border-bottom: 1px solid rgba(255, 255, 255, 0.12) !important;
            }}
            
            /* 頂部三線菜單按鈕 */
            QPushButton#btn_menu_toggle {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.14), stop:1 rgba(255, 255, 255, 0.03)) !important;
                border: 1px solid rgba(255, 255, 255, 0.15) !important;
                border-top: 1px solid rgba(255, 255, 255, 0.40) !important;
                border-radius: 10px !important;  /* 🎯 三線按鈕弧度 */
                padding: 4px;
            }}
            QPushButton#btn_menu_toggle:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.28), stop:1 rgba(255, 255, 255, 0.10)) !important;
                border-top: 1px solid rgba(255, 255, 255, 0.70) !important;
            }}
            
            QPushButton#btn_menu_toggle:pressed {{
                background-color: rgba(255, 255, 255, 0.08);
            }}

            QPushButton.nav_sidebar_btn {{
                background-color: transparent;
                border: none;
                border-radius: 8px;
            }}
            QPushButton.nav_sidebar_btn:hover {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
            QPushButton.nav_sidebar_btn:checked {{
                background-color: rgba(0, 122, 255, 0.3);
            }}

            /* ==================================================
               📌 區塊 12：QSplitter 分隔線樣式
               ================================================== */
            QSplitter::handle,
            CustomSplitter::handle,
            QSplitterHandle {{
                background-color: {c['glass_border']} !important;
                border: none !important;
                image: none !important; 
                border-radius: 3px;
            }}
            QSplitter::handle:hover,
            CustomSplitter::handle:hover,
            QSplitterHandle:hover {{
                background-color: {c['accent']} !important;
            }}
            QSplitter::handle:pressed,
            CustomSplitter::handle:pressed,
            QSplitterHandle:pressed {{
                background-color: #38ef7d !important;
            }}
            """  # 字串結束

    def apply_skin(self, theme_name):  # 套用主題皮
        self.win.current_theme = theme_name  # 記主題名稱
        
        # [修改點 1]
        stylesheet = self.get_skin_stylesheet(theme_name)  # 取得樣式表
        self.win.setStyleSheet(stylesheet)  # 設主窗樣式

        # 微軟毛玻璃
        if hasattr(self.win, 'winId'):  # 視窗有控制
            self.win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)  # 設背景透明
            c = self.win.current_theme_config  # 拿主題設定
            bg_hex = c.get('bg_dark_hex', '#0f172a')  # 拿暗底顏碼
            WindowBlurManager.enable_acrylic(int(self.win.winId()), bg_color_hex=bg_hex, alpha=180)  # 開丙烯模糊

        if self.win._settings and isinstance(self.win._settings, dict):  # 有設定檔存
            from config import _save_settings  # 載儲存函式
            self.win._settings["theme"] = theme_name  # 記新主題名
            _save_settings(self.win._settings)  # 存入設定檔

        stylesheet = self.get_skin_stylesheet(theme_name)  # 再產樣式表
        self.win.setStyleSheet(stylesheet)  # 刷新主樣式
        accent = self.win.current_theme_accent  # 拿強色顏碼
        c = self.win.current_theme_config  # 拿主題設定
        grad = c.get('gradient', (accent, accent, accent))  # 拿漸變色組

        if self.win.sidebar_btns:  # 有側欄按鈕
            active_btn = getattr(self.win, 'current_sidebar_btn', self.win.sidebar_btns[0])  # 拿目前按鈕
            self.win.update_sidebar_btn_styles(active_btn)  # 刷側欄樣式

        # 刷滑塊漸變
        for slider in (getattr(self.win, 'seek_slider', None), getattr(self.win, 'vol_slider', None)):  # 跑所有滑塊
            if slider:  # 滑塊物件在
                if hasattr(slider, 'set_theme_colors'):  # 有設色函式
                    slider.set_theme_colors(*grad)  # 設漸變色彩
                elif hasattr(slider, 'set_color'):  # 有單色函式
                    slider.set_color(accent)  # 設單色顏碼
                elif hasattr(slider, 'accent_color'):  # 有色屬性列
                    slider.accent_color = accent  # 改屬性顏碼
                    slider.update()  # 刷新滑塊圖

        if hasattr(self.win, 'bottom_bar') and self.win.bottom_bar:  # 底列物件在
            if self.win.isFullScreen():  # 全螢幕模式
                self.win.bottom_bar.setStyleSheet(stylesheet)  # 套全樣式表
            else:  # 視窗化模式
                self.win.bottom_bar.setStyleSheet("")  # 清底列樣式

            self.win.bottom_bar.style().unpolish(self.win.bottom_bar)  # 卸舊底樣式
            self.win.bottom_bar.style().polish(self.win.bottom_bar)  # 拋新底樣式
            
            for btn in self.win.bottom_bar.findChildren(QPushButton):  # 跑底列按鈕
                btn.style().unpolish(btn)  # 卸舊鈕樣式
                btn.style().polish(btn)  # 拋新鈕樣式
                btn.update()  # 刷新按鈕圖

            if hasattr(self.win, '_update_hw_btn_style'):  # 有硬解按鈕
                self.win._update_hw_btn_style()  # 刷硬解樣式

        if hasattr(self.win, 'screen_mgr'):  # 有屏管理器
            self.win.screen_mgr.update_screen_borders()  # 刷分屏邊框
            
        for dlg in self.win.findChildren(QDialog):  # 跑所有子窗
            if hasattr(dlg, 'update_dynamic_theme'):  # 子窗可刷色
                dlg.update_dynamic_theme()  # 刷子窗主題

        channel_panel = getattr(self.win, 'channel_panel', None)  # 拿頻道面板
        if channel_panel:  # 面板存在時
            for btn in channel_panel.findChildren(QPushButton):  # 跑面板按鈕
                role = btn.property("role")  # 拿按鈕角色
                if role in ["menu_btn", "filter_btn"]:  # 符合選單鈕
                    btn.style().unpolish(btn)  # 卸舊鈕樣式
                    btn.style().polish(btn)  # 拋新鈕樣式
                    btn.update()  # 刷新按鈕圖

        # [修改點 3]
        self.win.update()  # 刷新主視窗
        self.win.repaint()  # 重繪主視窗


class IconManager:  # 圖標管理器
    """SVG 圖示載入與動態著色管理器 (PyQt6 專用)"""  # 功能說明
    _ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")  # 設圖示路徑

    @classmethod  # 類別方法
    def get_icon(cls, name: str, color: str = None, size: int = 24) -> QIcon:  # 拿圖示物件
        icon_path = os.path.join(cls._ICON_DIR, f"{name}.svg")  # 建向量路徑
        if not os.path.exists(icon_path):  # 圖示檔不存在
            print(f"[IconManager] Warning: Icon missing -> {icon_path}")  # 印警告訊息
            return QIcon()  # 回傳空圖示

        if not color:  # 未指定顏色
            return QIcon(icon_path)  # 原色回圖示

        renderer = QSvgRenderer(icon_path)  # 建向量繪圖
        pixmap = QPixmap(size, size)  # 建點陣像素
        pixmap.fill(QColor(0, 0, 0, 0))  # 填全透明底

        painter = QPainter(pixmap)  # 建畫筆物件
        renderer.render(painter)  # 繪製向量圖
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)  # 設疊加模式
        painter.fillRect(pixmap.rect(), QColor(color))  # 填指定色彩
        painter.end()  # 結束畫筆繪

        return QIcon(pixmap)  # 回染色圖示