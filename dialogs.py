# dialogs.py
from config import *              # 匯入所有配置與 Qt 相關

from widgets import FlatGradientSlider  # 自定義漸變滑塊

# 整理說明：
# 類方法順序：__init__ → update_dynamic_theme → get_settings。
# 每個方法及主要代碼區塊（如佈局、按鈕、滑塊）均添加了繁體中文註釋，說明其用途。
# 所有代碼邏輯、變數、導入完全保持原樣，未作任何增刪改。
# 註釋清晰標示了每個 UI 組件的功能與設置項目的含義。

# ==================== 系統設置對話框 ====================
class SettingsDialog(QDialog):
    # ----- 建構子與 UI 初始化 -----
    def __init__(self, parent=None, config=None):
        """初始化設置對話框，綁定父視窗與設定資料"""
        super().__init__(parent)          # 呼叫父類建構子
        self.config = config or {}        # 保存設定字典（若無則為空）
        self.setWindowTitle("系統設置")    # 設定視窗標題
        self.setFixedSize(420, 320)       # 固定對話框尺寸

        # 若父視窗存在，則繼承其樣式表（達成主題同步）
        if parent:
            self.setStyleSheet(parent.styleSheet())

        # ---- 建立主佈局 ----
        layout = QVBoxLayout(self)        # 垂直佈局
        layout.setContentsMargins(24, 20, 24, 20)  # 設定邊距
        layout.setSpacing(16)             # 設定元件間距

        # 標題列
        title_label = QLabel("⚙  系統設置")
        title_label.setObjectName("settings_title")   # 供 QSS 樣式使用
        layout.addWidget(title_label)                 # 加入佈局

        # 分隔線
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        # 硬體加速核取方塊
        self.chk_hw = QCheckBox("啟用硬體加速解碼 (HW Acceleration)")
        self.chk_hw.setChecked(self.config.get("hwdec", True))  # 從設定讀取初始值
        layout.addWidget(self.chk_hw)

        # 自動播放上次頻道核取方塊
        self.chk_auto_play = QCheckBox("啟動時自動播放上次觀看頻道")
        self.chk_auto_play.setChecked(self.config.get("auto_play_last", False))
        layout.addWidget(self.chk_auto_play)

        # 緩衝區大小標籤（含數值顯示）
        cache_layout = QHBoxLayout()      # 水平佈局放置標籤與數值
        cache_label = QLabel("緩衝區大小")
        cache_label.setStyleSheet("font-size: 12px; font-weight: bold;")

        self.lbl_cache_val = QLabel(f"{self.config.get('cache_mb', 100)} MB")
        self.lbl_cache_val.setStyleSheet("font-size: 12px; font-weight: bold;")

        cache_layout.addWidget(cache_label)
        cache_layout.addStretch()          # 彈性空間將數值推至右側
        cache_layout.addWidget(self.lbl_cache_val)
        layout.addLayout(cache_layout)

        # 緩衝區大小滑塊（漸變樣式）
        self.slider_cache = FlatGradientSlider(Qt.Orientation.Horizontal)
        self.slider_cache.setRange(10, 500)                # 範圍 10~500 MB
        self.slider_cache.setValue(self.config.get("cache_mb", 100))
        # 滑塊值改變時同步更新顯示標籤
        self.slider_cache.valueChanged.connect(lambda v: self.lbl_cache_val.setText(f"{v} MB"))

        # 若父視窗存在，則套用其主題漸變色到滑塊
        if parent:
            grad = parent.current_theme_config.get('gradient')
            self.slider_cache.set_theme_colors(*grad)

        layout.addWidget(self.slider_cache)

        layout.addStretch()               # 加入彈性空間，將下方按鈕推至底部

        # ---- 按鈕區域 ----
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # 取消按鈕
        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)   # 關閉對話框（不儲存）

        # 儲存按鈕
        btn_save = QPushButton("保存設置")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self.accept)     # 關閉並返回 Accepted

        # 快捷鍵設定按鈕（呼叫父視窗的快捷鍵設定對話框）
        btn_hotkey = QPushButton("⌨️ 設定自定義快捷鍵")
        btn_hotkey.clicked.connect(lambda: parent.shortcut_mgr.open_hotkey_settings())
        layout.addWidget(btn_hotkey)              # 將此按鈕加入主佈局（注意位置）

        # 將取消與儲存加入按鈕佈局
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)              # 將按鈕佈局加入主佈局

    # ----- 動態更新主題（供外部調用）-----
    def update_dynamic_theme(self):
        """即時刷新對話框的主題樣式與滑塊漸變色（當父視窗主題變更時呼叫）"""
        if self.parent():                         # 若有父視窗
            self.parent_win = self.parent()       # 取得父視窗實例
            self.setStyleSheet(self.parent_win.styleSheet())  # 複製樣式表
            # 若父視窗有主題配置，則更新滑塊漸變色
            if hasattr(self.parent_win, 'current_theme_config'):
                grad = self.parent_win.current_theme_config.get('gradient')
                self.slider_cache.set_theme_colors(*grad)

    # ----- 獲取設定值（由父視窗呼叫）-----
    def get_settings(self):
        """返回使用者設定的字典，供主視窗儲存"""
        return {
            "hwdec": self.chk_hw.isChecked(),           # 硬體加速
            "auto_play_last": self.chk_auto_play.isChecked(),  # 自動播放上次
            "cache_mb": self.slider_cache.value()       # 緩衝區大小 (MB)
        }
