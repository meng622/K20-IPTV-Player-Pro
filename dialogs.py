# [代碼起點]
from config import *              # 匯入配置

from widgets import FlatGradientSlider  # 漸變滑塊

# ==================== 系統設置對話框 ====================
class SettingsDialog(QDialog):  # 設定視窗
    # ----- 建構子與 UI -----
    def __init__(self, parent=None, config=None):  # 初始化
        super().__init__(parent)          # 呼叫父類
        self.config = config or {}        # 讀取設定
        self.setWindowTitle("系統設置")    # 視窗標題
        self.setFixedSize(420, 320)       # 視窗尺寸

        if parent:  # 存在父窗
            self.setStyleSheet(parent.styleSheet())  # 同步樣式

        # ---- 建立主佈局 ----
        layout = QVBoxLayout(self)        # 垂直佈局
        layout.setContentsMargins(24, 20, 24, 20)  # 外邊距
        layout.setSpacing(16)             # 元件間距

        # 標題列
        title_label = QLabel("⚙  系統設置")  # 標題文字
        title_label.setObjectName("settings_title")   # 組件命名
        layout.addWidget(title_label)                 # 加入佈局

        # 分隔線
        line = QFrame()  # 建立分隔
        line.setFrameShape(QFrame.Shape.HLine)  # 水平線條
        layout.addWidget(line)  # 加入佈局

        # 硬體加速
        self.chk_hw = QCheckBox("啟用硬體加速解碼 (HW Acceleration)")  # 硬解勾選
        self.chk_hw.setChecked(self.config.get("hwdec", True))  # 讀取預設
        layout.addWidget(self.chk_hw)  # 加入佈局

        # 自動播放
        self.chk_auto_play = QCheckBox("啟動時自動播放上次觀看頻道")  # 自播勾選
        self.chk_auto_play.setChecked(self.config.get("auto_play_last", False))  # 讀取預設
        layout.addWidget(self.chk_auto_play)  # 加入佈局

        # 緩衝區文字
        cache_layout = QHBoxLayout()      # 水平佈局
        cache_label = QLabel("緩衝區大小")  # 緩衝標題
        cache_label.setStyleSheet("font-size: 12px; font-weight: bold;")  # 設定字體

        self.lbl_cache_val = QLabel(f"{self.config.get('cache_mb', 100)} MB")  # 緩衝數值
        self.lbl_cache_val.setStyleSheet("font-size: 12px; font-weight: bold;")  # 設定字體

        cache_layout.addWidget(cache_label)  # 加緩衝標
        cache_layout.addStretch()          # 彈性推開
        cache_layout.addWidget(self.lbl_cache_val)  # 加緩衝值
        layout.addLayout(cache_layout)  # 嵌入主排

        # 緩衝區滑塊
        self.slider_cache = FlatGradientSlider(Qt.Orientation.Horizontal)  # 緩衝滑塊
        self.slider_cache.setRange(10, 500)                # 滑塊範圍
        self.slider_cache.setValue(self.config.get("cache_mb", 100))  # 設定數值
        self.slider_cache.valueChanged.connect(lambda v: self.lbl_cache_val.setText(f"{v} MB"))  # 連接更新

        if parent:  # 存在父窗
            grad = parent.current_theme_config.get('gradient')  # 取得顏色
            self.slider_cache.set_theme_colors(*grad)  # 設定顏色

        layout.addWidget(self.slider_cache)  # 加入佈局

        layout.addStretch()               # 底部推開

        # ---- 按鈕區域 ----
        btn_layout = QHBoxLayout()  # 按鈕佈局
        btn_layout.addStretch()  # 左側推開

        # 取消按鈕
        btn_cancel = QPushButton("取消")  # 取消按鈕
        btn_cancel.setObjectName("btn_cancel")  # 按鈕命名
        btn_cancel.clicked.connect(self.reject)   # 綁定取消

        # 儲存按鈕
        btn_save = QPushButton("保存設置")  # 儲存按鈕
        btn_save.setObjectName("btn_save")  # 按鈕命名
        btn_save.clicked.connect(self.accept)     # 綁定保存

        # 快捷鍵按鈕
        btn_hotkey = QPushButton("⌨️ 設定自定義快捷鍵")  # 快捷按鈕
        btn_hotkey.clicked.connect(lambda: parent.shortcut_mgr.open_hotkey_settings())  # 開快捷窗
        layout.addWidget(btn_hotkey)              # 加快捷鈕

        btn_layout.addWidget(btn_cancel)  # 加取消鈕
        btn_layout.addWidget(btn_save)  # 加儲存鈕
        layout.addLayout(btn_layout)              # 加按鈕排

    # ----- 動態主題 -----
    def update_dynamic_theme(self):  # 刷新主題
        if self.parent():                         # 存在父窗
            self.parent_win = self.parent()       # 取得父窗
            self.setStyleSheet(self.parent_win.styleSheet())  # 套用樣式
            if hasattr(self.parent_win, 'current_theme_config'):  # 有主題設定
                grad = self.parent_win.current_theme_config.get('gradient')  # 取得顏色
                self.slider_cache.set_theme_colors(*grad)  # 套用漸變

    # ----- 獲取設定 -----
    def get_settings(self):  # 回傳設定
        return {  # 字典回傳
            "hwdec": self.chk_hw.isChecked(),           # 硬解狀態
            "auto_play_last": self.chk_auto_play.isChecked(),  # 自播狀態
            "cache_mb": self.slider_cache.value()       # 緩衝大小
        }  # 結尾字典
# [代碼終點]