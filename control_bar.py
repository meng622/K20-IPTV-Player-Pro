# control_bar.py
from config import *  # 匯入配置

from skin import IconManager
from widgets import FlatGradientSlider

# =================================================================================

# 整理說明：
# 所有方法按 初始化與UI構建 → 控件自適應 → 淡入淡出動畫 → 事件處理 的順序排列。
# 每個方法前添加了繁體中文註釋（可多於6字），明確功能與用途。
# 所有代碼邏輯、變數、導入、類結構完全保持原樣，未作任何增刪改。
# 亂碼部分已修正為正確的中文（如「匯入配置」、「主題設定」、「畫中畫」等）。

# =================================================================================
# 播放器控制栏组件
# =================================================================================
class PlayerControlBar(QWidget):
    # ----- 初始化与UI构建 ------------------------------------------------------------------------------------------------------------
    def __init__(self, main_win):
        """建構子：綁定主視窗並初始化控制欄"""
        super().__init__(main_win)
        self.main_win = main_win
        self.setFixedHeight(100)
        self.setObjectName("bottom_bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._is_fading = False
        self._init_ui()

    def _set_btn_svg_icon(self, btn, icon_name, icon_size=None):
        """設定按鈕的 SVG 圖示（自動適應按鈕尺寸）"""
        if icon_size is not None:
            btn.setIconSize(icon_size)

        cur_size = btn.iconSize()
        if cur_size.width() == 0 or cur_size.height() == 0:
            cur_size = QSize(18, 18)
            btn.setIconSize(cur_size)

        icon = IconManager.get_icon(icon_name, size=cur_size.width())
        btn.setIcon(icon)

    def _init_ui(self):
        """構建控制欄的所有子組件與佈局"""
        bottom_main_layout = QVBoxLayout(self)
        bottom_main_layout.setContentsMargins(16, 4, 16, 8)
        bottom_main_layout.setSpacing(0)

        # ---- 上方進度條區域 ----
        top_seek_layout = QHBoxLayout()
        top_seek_layout.setContentsMargins(0, 0, 0, 0)
        top_seek_layout.setSpacing(12)

        self.lbl_current_time = QLabel("00:00")
        self.main_win.lbl_current_time = self.lbl_current_time

        self.seek_slider = FlatGradientSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.sliderPressed.connect(self.main_win.on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self.main_win.on_seek_released)
        self.main_win.seek_slider = self.seek_slider

        self.lbl_total_time = QLabel("00:00")
        self.main_win.lbl_total_time = self.lbl_total_time

        top_seek_layout.addWidget(self.lbl_current_time)
        top_seek_layout.addWidget(self.seek_slider, stretch=1)
        top_seek_layout.addWidget(self.lbl_total_time)

        # ---- 下方控制按鈕區域 ----
        self.bottom_controls_layout = QHBoxLayout()
        self.bottom_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_controls_layout.setSpacing(6)

        # 左側核心控制（永遠顯示）
        self.play_btn = QPushButton("")
        self.play_btn.setFixedSize(64, 64)
        self.play_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.play_btn.setObjectName("play_btn")
        self.play_btn.clicked.connect(self.main_win.toggle_play)
        self.main_win.play_btn = self.play_btn
        self.main_win.btn_play_pause = self.play_btn
        self._set_btn_svg_icon(self.play_btn, "play", QSize(64, 64))

        self.btn_stop = QPushButton("")
        self.btn_stop.setFixedSize(42, 42)
        self.btn_stop.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.btn_stop.setProperty("role", "media_control_btn")
        self.btn_stop.clicked.connect(self.main_win.stop_play)
        self._set_btn_svg_icon(self.btn_stop, "stop", QSize(42, 42))

        self.btn_rewind = QPushButton("")
        self.btn_rewind.setFixedSize(32, 32)
        self.btn_rewind.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.btn_rewind.setProperty("role", "media_control_btn")
        self.btn_rewind.clicked.connect(lambda: self.main_win.seek_offset(-5))
        self._set_btn_svg_icon(self.btn_rewind, "rewind", QSize(24, 24))

        self.btn_forward = QPushButton("")
        self.btn_forward.setFixedSize(32, 32)
        self.btn_forward.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.btn_forward.setProperty("role", "media_control_btn")
        self.btn_forward.clicked.connect(lambda: self.main_win.seek_offset(5))
        self._set_btn_svg_icon(self.btn_forward, "forward", QSize(24, 24))

        self.btn_mute = QPushButton("")
        self.btn_mute.setFixedSize(32, 32)
        self.btn_mute.setProperty("role", "media_control_btn")
        self.btn_mute.clicked.connect(self.main_win.toggle_mute)
        self.main_win.btn_mute = self.btn_mute
        self._set_btn_svg_icon(self.btn_mute, "volume", QSize(24, 24))

        self.vol_slider = FlatGradientSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setFixedHeight(32)
        self.vol_slider.valueChanged.connect(self.main_win.set_volume)
        self.main_win.vol_slider = self.vol_slider
        self.main_win.volume_slider = self.vol_slider

        # 中間功能按鈕（純圖示，可依寬度隱藏）
        self.btn_screen_layout = QPushButton("")
        self.btn_screen_layout.setFixedSize(32, 32)
        self.btn_screen_layout.setProperty("role", "menu_btn")
        self.btn_screen_layout.setToolTip("分屏")
        self.btn_screen_layout.clicked.connect(self.main_win.show_screen_layout_menu)
        self.main_win.btn_screen_layout = self.btn_screen_layout
        self._set_btn_svg_icon(self.btn_screen_layout, "layout", QSize(24, 24))

        self.btn_pip = QPushButton("")
        self.btn_pip.setFixedSize(32, 32)
        self.btn_pip.setProperty("role", "menu_btn")
        self.btn_pip.setToolTip("畫中畫")
        self.btn_pip.clicked.connect(self.main_win.toggle_pip)
        self.main_win.btn_pip = self.btn_pip
        self._set_btn_svg_icon(self.btn_pip, "pip", QSize(24, 24))

        self.btn_skin = QPushButton("")
        self.btn_skin.setFixedSize(32, 32)
        self.btn_skin.setProperty("role", "menu_btn")
        self.btn_skin.setToolTip("主題設定")
        self.btn_skin.clicked.connect(self.main_win.show_skin_menu)
        self.main_win.btn_skin = self.btn_skin
        self._set_btn_svg_icon(self.btn_skin, "palette", QSize(24, 24))

        self.btn_hw = QPushButton("")
        self.btn_hw.setFixedSize(32, 32)
        self.btn_hw.setProperty("role", "menu_btn")
        self.btn_hw.setToolTip("HW: On" if self.main_win.hw_enabled else "HW: Off")
        self.btn_hw.clicked.connect(self.main_win.toggle_hw)
        self.main_win.btn_hw = self.btn_hw
        self._set_btn_svg_icon(self.btn_hw, "cpu", QSize(24, 24))

        self.btn_aspect = QPushButton("")
        self.btn_aspect.setFixedSize(32, 32)
        self.btn_aspect.setProperty("role", "menu_btn")
        self.btn_aspect.setToolTip("比例")
        self.btn_aspect.clicked.connect(self.main_win.show_aspect_menu)
        self.main_win.btn_aspect = self.btn_aspect
        self._set_btn_svg_icon(self.btn_aspect, "aspect", QSize(24, 24))

        self.btn_audio = QPushButton("")
        self.btn_audio.setFixedSize(32, 32)
        self.btn_audio.setProperty("role", "menu_btn")
        self.btn_audio.setToolTip("音軌")
        self.btn_audio.clicked.connect(self.main_win.show_audio_menu)
        self.main_win.btn_audio = self.btn_audio
        self._set_btn_svg_icon(self.btn_audio, "audio", QSize(24, 24))

        self.btn_sub = QPushButton("")
        self.btn_sub.setFixedSize(32, 32)
        self.btn_sub.setProperty("role", "menu_btn")
        self.btn_sub.setToolTip("字幕")
        self.btn_sub.clicked.connect(self.main_win.show_subtitle_menu)
        self.main_win.btn_sub = self.btn_sub
        self._set_btn_svg_icon(self.btn_sub, "subtitle", QSize(24, 24))
        
        # ℹ️ 播放統計/資訊按鈕 (i)
        self.btn_osd = QPushButton("")
        self.btn_osd.setFixedSize(32, 32)
        self.btn_osd.setProperty("role", "menu_btn")
        self.btn_osd.setToolTip("播放統計/資訊 (i)")
        self.btn_osd.clicked.connect(self.main_win.show_osd)
        self.main_win.btn_osd = self.btn_osd
        self._set_btn_svg_icon(self.btn_osd, "osd", QSize(24, 24))

        # 右側必留按鈕（永遠顯示）
        self.btn_snapshot = QPushButton("")
        self.btn_snapshot.setFixedSize(64, 64)
        self.btn_snapshot.setProperty("role", "media_control_btn")
        self.btn_snapshot.setToolTip("截圖")
        self.btn_snapshot.clicked.connect(self.main_win.take_snapshot)
        self.main_win.btn_snapshot = self.btn_snapshot
        self._set_btn_svg_icon(self.btn_snapshot, "camera", QSize(64, 64))

        self.btn_fullscreen = QPushButton("")
        self.btn_fullscreen.setFixedSize(64, 64)
        self.btn_fullscreen.setProperty("role", "media_control_btn")
        self.btn_fullscreen.setToolTip("全屏")
        self.btn_fullscreen.clicked.connect(self.main_win.toggle_fullscreen)
        self.main_win.btn_fullscreen = self.btn_fullscreen
        self._set_btn_svg_icon(self.btn_fullscreen, "fullscreen", QSize(64, 64))

        # 統一 menu_btn 樣式（套用皮膚）
        for btn in [self.btn_screen_layout, self.btn_pip, self.btn_skin,
                    self.btn_hw, self.btn_aspect, self.btn_audio, self.btn_sub]:
            btn.setStyleSheet("")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # ---- 組裝佈局 ----
        align_bottom = Qt.AlignmentFlag.AlignBottom

        self.bottom_controls_layout.addWidget(self.play_btn, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_stop, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_rewind, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_forward, alignment=align_bottom)
        self.bottom_controls_layout.addSpacing(8)
        self.bottom_controls_layout.addWidget(self.btn_mute, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.vol_slider, alignment=align_bottom)
        self.bottom_controls_layout.addStretch()
        self.bottom_controls_layout.addWidget(self.btn_screen_layout, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_pip, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_skin, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_hw, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_aspect, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_audio, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_sub, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_osd, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_snapshot, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_fullscreen, alignment=align_bottom)

        bottom_main_layout.addLayout(top_seek_layout)
        bottom_main_layout.addLayout(self.bottom_controls_layout)

        # 初始化強制全部顯示
        self._force_show_all()

    def _force_show_all(self):
        """強制所有中間按鈕可見（避免初始狀態被隱藏）"""
        for btn in [self.btn_screen_layout, self.btn_pip, self.btn_skin,
                    self.btn_hw, self.btn_aspect, self.btn_audio, self.btn_sub,
                    self.btn_snapshot, self.btn_fullscreen]:
            if btn:
                btn.setVisible(True)
    
    
    # ----- 控件自适应（按視窗寬度隱藏中間按鈕）---------------------------------------------------------------------------------
    def auto_adjust_controls(self):
        """
        根據控制欄寬度動態顯示或隱藏中間功能按鈕。
        左右兩側核心控制永遠保留，中間按鈕從最不重要（字幕）開始隱藏。
        """
        if self.main_win.is_pip_mode:
            return

        bar_w = self.width()
        if bar_w <= 0:
            return

        spacing = self.bottom_controls_layout.spacing()   # 6
        margin = 16 * 2                                    # 32
        min_gap = 5                                        # 貼近 slider 先開始隱藏

        # 左側核心（固定寬度，不查詢 widget）
        left_need = 64 + 42 + 32 + 32 + 32 + 80   # widgets
        left_need += spacing * 4                   # 4 個內部 spacing
        left_need += 8                             # addSpacing(8)

        # 右側必留
        right_need = 64 + 64 + spacing             # snapshot + fullscreen + 1 spacing

        # 中間可隱藏（7 個純 icon 32x32）
        middle_items = [
            self.btn_screen_layout,
            self.btn_pip,
            self.btn_skin,
            self.btn_hw,
            self.btn_aspect,
            self.btn_audio,
            self.btn_sub,
            self.btn_osd,
        ]
        middle_unit = 32 + spacing                   # 每個按鈕連 spacing
        middle_total = 32 * len(middle_items) + spacing * max(0, len(middle_items) - 1)

        # 全部顯示所需總寬度
        total_need = left_need + right_need + middle_total + margin + min_gap

        # 夠位 → 全部顯示
        if bar_w >= total_need:
            for btn in middle_items:
                if btn:
                    btn.setVisible(True)
            self.bottom_controls_layout.activate()
            return

        # 不夠位：由最尾（最優先保留）開始逐個加
        available = bar_w - left_need - right_need - margin - min_gap
        if available < 0:
            available = 0

        # 逐個計：由 sub → audio → aspect → hw → skin → pip → screen_layout
        cumulative = 0
        show_map = {}
        for i in range(len(middle_items) - 1, -1, -1):
            w = 32
            if i < len(middle_items) - 1:
                w += spacing
            cumulative += w
            show_map[i] = cumulative <= available

        for i, btn in enumerate(middle_items):
            if btn:
                btn.setVisible(show_map.get(i, False))

        # 確保左右永遠顯示
        for btn in [self.play_btn, self.btn_stop, self.btn_rewind,
                    self.btn_forward, self.btn_mute, self.vol_slider,
                    self.btn_snapshot, self.btn_fullscreen]:
            if btn:
                btn.setVisible(True)

        self.bottom_controls_layout.activate()
        self.update()
    
    
    # ----- 淡入淡出動畫（用於全屏模式）-------------------------------------------------------------------------------------------
    def fade_in(self):
        """終極流暢版：QTimer 手動步進淡入"""
        self.show()
        self.setWindowOpacity(0.0)
        if hasattr(self, '_fade_timer') and self._fade_timer:
            self._fade_timer.stop()
        
        self._fade_step = 0.0
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(16)  # 約 60 FPS
        self._fade_timer.timeout.connect(self._do_fade_in)
        self._fade_timer.start()
        self._is_fading = True

    def _do_fade_in(self):
        """淡入動畫的逐幀執行（每次增加 0.15，快速）"""
        self._fade_step += 0.15
        if self._fade_step >= 1.0:
            self.setWindowOpacity(1.0)
            self._fade_timer.stop()
            self._is_fading = False
        else:
            self.setWindowOpacity(self._fade_step)

    def fade_out(self):
        """終極流暢版：QTimer 手動步進淡出"""
        if self._is_fading:
            return
        if hasattr(self, '_fade_timer') and self._fade_timer:
            self._fade_timer.stop()
        
        self._fade_step = self.windowOpacity()
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(16)
        self._fade_timer.timeout.connect(self._do_fade_out)
        self._fade_timer.start()

    def _do_fade_out(self):
        """淡出動畫的逐幀執行（每次減少 0.06，慢慢消失）"""
        self._fade_step -= 0.06
        if self._fade_step <= 0.0:
            self.setWindowOpacity(0.0)
            self._fade_timer.stop()
            self.hide()
        else:
            self.setWindowOpacity(self._fade_step)
    
    
    # ----- 事件處理 -------------------------------------------------------------------------------------------------------------------
    def resizeEvent(self, event):
        """視窗大小改變時重新調整控件顯示"""
        super().resizeEvent(event)
        self.auto_adjust_controls()

    def enterEvent(self, event):
        """🎯 B3 修復：鼠標進入控制欄，停止隱藏倒數"""
        self.main_win.hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """🎯 B3 修復：鼠標離開控制欄，重啟隱藏倒數（僅全屏時）"""
        if self.main_win.isFullScreen():
            self.main_win.hide_timer.start()
        super().leaveEvent(event)
