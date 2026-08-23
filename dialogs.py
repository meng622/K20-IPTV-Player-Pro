# dialogs.py
from config import *
from widgets import FlatGradientSlider

# ==================== 系統設置對話框 ====================
class SettingsDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config or {}
        self.setWindowTitle("系統設置")
        self.setFixedSize(420, 320)
        
        # 🎯 同步主題樣式
        if parent:
            self.setStyleSheet(parent.styleSheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title_label = QLabel("⚙  系統設置")
        title_label.setObjectName("settings_title")
        layout.addWidget(title_label)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        self.chk_hw = QCheckBox("啟用硬體加速解碼 (HW Acceleration)")
        self.chk_hw.setChecked(self.config.get("hwdec", True))
        layout.addWidget(self.chk_hw)

        self.chk_auto_play = QCheckBox("啟動時自動播放上次觀看頻道")
        self.chk_auto_play.setChecked(self.config.get("auto_play_last", False))
        layout.addWidget(self.chk_auto_play)

        cache_layout = QHBoxLayout()
        cache_label = QLabel("緩衝區大小")
        cache_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        
        self.lbl_cache_val = QLabel(f"{self.config.get('cache_mb', 100)} MB")
        self.lbl_cache_val.setStyleSheet("font-size: 12px; font-weight: bold;")
        
        cache_layout.addWidget(cache_label)
        cache_layout.addStretch()
        cache_layout.addWidget(self.lbl_cache_val)
        layout.addLayout(cache_layout)

        self.slider_cache = FlatGradientSlider(Qt.Orientation.Horizontal)
        self.slider_cache.setRange(10, 500)
        self.slider_cache.setValue(self.config.get("cache_mb", 100))
        self.slider_cache.valueChanged.connect(lambda v: self.lbl_cache_val.setText(f"{v} MB"))

        # 🎯 同步漸變色
        if parent and hasattr(parent, 'current_theme_config'):
            grad = parent.current_theme_config.get('gradient')
            self.slider_cache.set_theme_colors(*grad)

        layout.addWidget(self.slider_cache)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("保存設置")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self.accept)
        
        # 加入按鈕連去快捷鍵設定
        btn_hotkey = QPushButton("⌨️ 設定自定義快捷鍵")
        btn_hotkey.clicked.connect(lambda: parent.shortcut_mgr.open_hotkey_settings())
        layout.addWidget(btn_hotkey)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def update_dynamic_theme(self):
        # 🎯 即時刷新主題
        if self.parent():
            self.parent_win = self.parent()
            self.setStyleSheet(self.parent_win.styleSheet())
            if hasattr(self.parent_win, 'current_theme_config'):
                grad = self.parent_win.current_theme_config.get('gradient')
                self.slider_cache.set_theme_colors(*grad)

    def get_settings(self):
        return {
            "hwdec": self.chk_hw.isChecked(),
            "auto_play_last": self.chk_auto_play.isChecked(),
            "cache_mb": self.slider_cache.value()
        }