# control_bar.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QSize
from skin import IconManager
from widgets import FlatGradientSlider


class PlayerControlBar(QWidget):
    def __init__(self, main_win):
        super().__init__(main_win)
        self.main_win = main_win
        self.setFixedHeight(100)
        self.setObjectName("bottom_bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_ui()

    def _set_btn_svg_icon(self, btn, icon_name, icon_size=None):
        if icon_size is not None:
            btn.setIconSize(icon_size)

        cur_size = btn.iconSize()
        if cur_size.width() == 0 or cur_size.height() == 0:
            cur_size = QSize(18, 18)
            btn.setIconSize(cur_size)

        icon = IconManager.get_icon(icon_name, size=cur_size.width())
        btn.setIcon(icon)

    def _init_ui(self):
        bottom_main_layout = QVBoxLayout(self)
        bottom_main_layout.setContentsMargins(16, 4, 16, 8)
        bottom_main_layout.setSpacing(0)

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

        self.bottom_controls_layout = QHBoxLayout()
        self.bottom_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_controls_layout.setSpacing(6)

        # ===== 左邊核心控制（永遠顯示）=====
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

        # ===== 中間功能按鈕（純 icon，可隱藏）=====
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

        # ===== 右邊必留（永遠顯示）=====
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

        # 統一 menu_btn 樣式
        for btn in [self.btn_screen_layout, self.btn_pip, self.btn_skin,
                    self.btn_hw, self.btn_aspect, self.btn_audio, self.btn_sub]:
            btn.setStyleSheet("")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # 兼容舊版 HW 樣式更新（如果 main_win 有呢個方法）
        #if hasattr(self.main_win, '_update_hw_btn_style'):
            #self.main_win._update_hw_btn_style()

        # ===== Layout =====
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
        self.bottom_controls_layout.addWidget(self.btn_snapshot, alignment=align_bottom)
        self.bottom_controls_layout.addWidget(self.btn_fullscreen, alignment=align_bottom)

        bottom_main_layout.addLayout(top_seek_layout)
        bottom_main_layout.addLayout(self.bottom_controls_layout)

        # 初始化強制全部顯示
        self._force_show_all()

    def _force_show_all(self):
        for btn in [self.btn_screen_layout, self.btn_pip, self.btn_skin,
                    self.btn_hw, self.btn_aspect, self.btn_audio, self.btn_sub,
                    self.btn_snapshot, self.btn_fullscreen]:
            if btn:
                btn.setVisible(True)

    def auto_adjust_controls(self):
        """
        中間按鈕逐個隱藏；左右兩邊永遠保留。
        全部用固定寬度，唔再依賴 sizeHint/width()。
        """
        if getattr(self.main_win, 'is_pip_mode', False):
            return

        bar_w = self.width()
        if bar_w <= 0:
            return

        spacing = self.bottom_controls_layout.spacing()   # 6
        margin = 16 * 2                                    # 32
        min_gap = 5                                        # 貼近 slider 先開始隱藏

        # 左邊核心（固定寬度，唔使問 widget）
        left_need = 64 + 42 + 32 + 32 + 32 + 80   # widgets
        left_need += spacing * 4                   # 4 個內部 spacing
        left_need += 8                             # addSpacing(8)

        # 右邊必留
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

        # 逐個計：由 sub→audio→aspect→hw→skin→pip→screen_layout
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.auto_adjust_controls()