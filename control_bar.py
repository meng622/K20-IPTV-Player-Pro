# [代碼起點]
from config import *  # 匯入配置

from skin import IconManager  # 圖案管理
from widgets import FlatGradientSlider  # 漸變滑塊

# =================================================================================
# 控制欄類
# =================================================================================
class PlayerControlBar(QWidget):  # 控制欄類
    # ----- 初始化與UI -----
    def __init__(self, main_win):  # 初始化
        super().__init__(main_win)  # 基類初始
        self.main_win = main_win  # 主視窗
        self.setFixedHeight(100)  # 固定高度
        self.setObjectName("bottom_bar")  # 組件命名
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # 背景渲染
        self._is_fading = False  # 動畫狀態
        self._init_ui()  # 構建介面

    def _set_btn_svg_icon(self, btn, icon_name, icon_size=None):  # 設定圖示
        if icon_size is not None:  # 指定大小
            btn.setIconSize(icon_size)  # 套用尺寸

        cur_size = btn.iconSize()  # 取得尺寸
        if cur_size.width() == 0 or cur_size.height() == 0:  # 尺寸為空
            cur_size = QSize(18, 18)  # 預設尺寸
            btn.setIconSize(cur_size)  # 套用預設

        icon = IconManager.get_icon(icon_name, size=cur_size.width())  # 載入圖示
        btn.setIcon(icon)  # 綁定圖示

    def _init_ui(self):  # UI構建
        bottom_main_layout = QVBoxLayout(self)  # 垂直佈局
        bottom_main_layout.setContentsMargins(16, 4, 16, 8)  # 外邊距
        bottom_main_layout.setSpacing(0)  # 間距歸零

        # ---- 進度條 ----
        top_seek_layout = QHBoxLayout()  # 水平佈局
        top_seek_layout.setContentsMargins(0, 0, 0, 0)  # 外邊距
        top_seek_layout.setSpacing(12)  # 組件間距

        self.lbl_current_time = QLabel("00:00")  # 當前時間
        self.main_win.lbl_current_time = self.lbl_current_time  # 綁定全域

        self.seek_slider = FlatGradientSlider(Qt.Orientation.Horizontal)  # 進度滑塊
        self.seek_slider.setRange(0, 1000)  # 滑塊範圍
        self.seek_slider.setValue(0)  # 初始歸零
        self.seek_slider.sliderPressed.connect(self.main_win.on_seek_pressed)  # 按下滑塊
        self.seek_slider.sliderReleased.connect(self.main_win.on_seek_released)  # 釋放滑塊
        self.main_win.seek_slider = self.seek_slider  # 綁定全域

        self.lbl_total_time = QLabel("00:00")  # 總計時間
        self.main_win.lbl_total_time = self.lbl_total_time  # 綁定全域

        top_seek_layout.addWidget(self.lbl_current_time)  # 加當前時
        top_seek_layout.addWidget(self.seek_slider, stretch=1)  # 加進度條
        top_seek_layout.addWidget(self.lbl_total_time)  # 加總時間

        # ---- 按鈕區 ----
        self.bottom_controls_layout = QHBoxLayout()  # 水平佈局
        self.bottom_controls_layout.setContentsMargins(0, 0, 0, 0)  # 外邊距
        self.bottom_controls_layout.setSpacing(6)  # 組件間距

        # 左側控制
        self.play_btn = QPushButton("")  # 播放按鈕
        self.play_btn.setFixedSize(64, 64)  # 按鈕尺寸
        self.play_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)  # 縮放策略
        self.play_btn.setObjectName("play_btn")  # 按鈕命名
        self.play_btn.clicked.connect(self.main_win.toggle_play)  # 綁定播放
        self.main_win.play_btn = self.play_btn  # 綁定全域
        self.main_win.btn_play_pause = self.play_btn  # 綁定全域
        self._set_btn_svg_icon(self.play_btn, "play", QSize(64, 64))  # 播放圖示

        self.btn_stop = QPushButton("")  # 停止按鈕
        self.btn_stop.setFixedSize(42, 42)  # 按鈕尺寸
        self.btn_stop.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)  # 縮放策略
        self.btn_stop.setProperty("role", "media_control_btn")  # 角色屬性
        self.btn_stop.clicked.connect(self.main_win.stop_play)  # 綁定停止
        self._set_btn_svg_icon(self.btn_stop, "stop", QSize(42, 42))  # 停止圖示

        self.btn_rewind = QPushButton("")  # 快退按鈕
        self.btn_rewind.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_rewind.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)  # 縮放策略
        self.btn_rewind.setProperty("role", "media_control_btn")  # 角色屬性
        self.btn_rewind.clicked.connect(lambda: self.main_win.seek_offset(-5))  # 快退5秒
        self._set_btn_svg_icon(self.btn_rewind, "rewind", QSize(24, 24))  # 快退圖示

        self.btn_forward = QPushButton("")  # 快進按鈕
        self.btn_forward.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_forward.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)  # 縮放策略
        self.btn_forward.setProperty("role", "media_control_btn")  # 角色屬性
        self.btn_forward.clicked.connect(lambda: self.main_win.seek_offset(5))  # 快進5秒
        self._set_btn_svg_icon(self.btn_forward, "forward", QSize(24, 24))  # 快進圖示

        self.btn_mute = QPushButton("")  # 靜音按鈕
        self.btn_mute.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_mute.setProperty("role", "media_control_btn")  # 角色屬性
        self.btn_mute.clicked.connect(self.main_win.toggle_mute)  # 綁定靜音
        self.main_win.btn_mute = self.btn_mute  # 綁定全域
        self._set_btn_svg_icon(self.btn_mute, "volume", QSize(24, 24))  # 音量圖示

        self.vol_slider = FlatGradientSlider(Qt.Orientation.Horizontal)  # 音量滑塊
        self.vol_slider.setRange(0, 100)  # 音量範圍
        self.vol_slider.setValue(100)  # 預設滿音
        self.vol_slider.setFixedWidth(80)  # 固定寬度
        self.vol_slider.setFixedHeight(32)  # 固定高度
        self.vol_slider.valueChanged.connect(self.main_win.set_volume)  # 調整音量
        self.main_win.vol_slider = self.vol_slider  # 綁定全域
        self.main_win.volume_slider = self.vol_slider  # 綁定全域

        # 中間功能
        self.btn_screen_layout = QPushButton("")  # 分屏按鈕
        self.btn_screen_layout.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_screen_layout.setProperty("role", "menu_btn")  # 角色屬性
        self.btn_screen_layout.setToolTip("分屏")  # 工具提示
        self.btn_screen_layout.clicked.connect(self.main_win.show_screen_layout_menu)  # 觸發分屏
        self.main_win.btn_screen_layout = self.btn_screen_layout  # 綁定全域
        self._set_btn_svg_icon(self.btn_screen_layout, "layout", QSize(24, 24))  # 分屏圖示

        self.btn_pip = QPushButton("")  # 畫畫按鈕
        self.btn_pip.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_pip.setProperty("role", "menu_btn")  # 角色屬性
        self.btn_pip.setToolTip("畫中畫")  # 工具提示
        self.btn_pip.clicked.connect(self.main_win.toggle_pip)  # 觸發畫畫
        self.main_win.btn_pip = self.btn_pip  # 綁定全域
        self._set_btn_svg_icon(self.btn_pip, "pip", QSize(24, 24))  # 畫畫圖示

        self.btn_skin = QPushButton("")  # 主題按鈕
        self.btn_skin.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_skin.setProperty("role", "menu_btn")  # 角色屬性
        self.btn_skin.setToolTip("主題設定")  # 工具提示
        self.btn_skin.clicked.connect(self.main_win.show_skin_menu)  # 開啟主題
        self.main_win.btn_skin = self.btn_skin  # 綁定全域
        self._set_btn_svg_icon(self.btn_skin, "palette", QSize(24, 24))  # 主題圖示

        self.btn_hw = QPushButton("")  # 硬解按鈕
        self.btn_hw.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_hw.setProperty("role", "menu_btn")  # 角色屬性
        self.btn_hw.setToolTip("HW: On" if self.main_win.hw_enabled else "HW: Off")  # 硬解提示
        self.btn_hw.clicked.connect(self.main_win.toggle_hw)  # 切換硬解
        self.main_win.btn_hw = self.btn_hw  # 綁定全域
        self._set_btn_svg_icon(self.btn_hw, "cpu", QSize(24, 24))  # 硬解圖示

        self.btn_aspect = QPushButton("")  # 比例按鈕
        self.btn_aspect.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_aspect.setProperty("role", "menu_btn")  # 角色屬性
        self.btn_aspect.setToolTip("比例")  # 工具提示
        self.btn_aspect.clicked.connect(self.main_win.show_aspect_menu)  # 開啟比例
        self.main_win.btn_aspect = self.btn_aspect  # 綁定全域
        self._set_btn_svg_icon(self.btn_aspect, "aspect", QSize(24, 24))  # 比例圖示

        self.btn_audio = QPushButton("")  # 音軌按鈕
        self.btn_audio.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_audio.setProperty("role", "menu_btn")  # 角色屬性
        self.btn_audio.setToolTip("音軌")  # 工具提示
        self.btn_audio.clicked.connect(self.main_win.show_audio_menu)  # 開啟音軌
        self.main_win.btn_audio = self.btn_audio  # 綁定全域
        self._set_btn_svg_icon(self.btn_audio, "audio", QSize(24, 24))  # 音軌圖示

        self.btn_sub = QPushButton("")  # 字幕按鈕
        self.btn_sub.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_sub.setProperty("role", "menu_btn")  # 角色屬性
        self.btn_sub.setToolTip("字幕")  # 工具提示
        self.btn_sub.clicked.connect(self.main_win.show_subtitle_menu)  # 開啟字幕
        self.main_win.btn_sub = self.btn_sub  # 綁定全域
        self._set_btn_svg_icon(self.btn_sub, "subtitle", QSize(24, 24))  # 字幕圖示
        
        # 統計資訊
        self.btn_osd = QPushButton("")  # 資訊按鈕
        self.btn_osd.setFixedSize(32, 32)  # 按鈕尺寸
        self.btn_osd.setProperty("role", "menu_btn")  # 角色屬性
        self.btn_osd.setToolTip("播放統計/資訊 (i)")  # 工具提示
        self.btn_osd.clicked.connect(self.main_win.show_osd)  # 開啟資訊
        self.main_win.btn_osd = self.btn_osd  # 綁定全域
        self._set_btn_svg_icon(self.btn_osd, "osd", QSize(24, 24))  # 資訊圖示

        # 右側控制
        self.btn_snapshot = QPushButton("")  # 截圖按鈕
        self.btn_snapshot.setFixedSize(64, 64)  # 按鈕尺寸
        self.btn_snapshot.setProperty("role", "media_control_btn")  # 角色屬性
        self.btn_snapshot.setToolTip("截圖")  # 工具提示
        self.btn_snapshot.clicked.connect(self.main_win.take_snapshot)  # 觸發截圖
        self.main_win.btn_snapshot = self.btn_snapshot  # 綁定全域
        self._set_btn_svg_icon(self.btn_snapshot, "camera", QSize(64, 64))  # 截圖圖示

        self.btn_fullscreen = QPushButton("")  # 全屏按鈕
        self.btn_fullscreen.setFixedSize(64, 64)  # 按鈕尺寸
        self.btn_fullscreen.setProperty("role", "media_control_btn")  # 角色屬性
        self.btn_fullscreen.setToolTip("全屏")  # 工具提示
        self.btn_fullscreen.clicked.connect(self.main_win.toggle_fullscreen)  # 切換全屏
        self.main_win.btn_fullscreen = self.btn_fullscreen  # 綁定全域
        self._set_btn_svg_icon(self.btn_fullscreen, "fullscreen", QSize(64, 64))  # 全屏圖示

        # 刷新樣式
        for btn in [self.btn_screen_layout, self.btn_pip, self.btn_skin,
                    self.btn_hw, self.btn_aspect, self.btn_audio, self.btn_sub]:
            btn.setStyleSheet("")  # 清空樣式
            btn.style().unpolish(btn)  # 取消樣式
            btn.style().polish(btn)  # 套用樣式

        # ---- 組合佈局 ----
        align_bottom = Qt.AlignmentFlag.AlignBottom  # 底端對齊

        self.bottom_controls_layout.addWidget(self.play_btn, alignment=align_bottom)  # 加播放鈕
        self.bottom_controls_layout.addWidget(self.btn_stop, alignment=align_bottom)  # 加停止鈕
        self.bottom_controls_layout.addWidget(self.btn_rewind, alignment=align_bottom)  # 加快退鈕
        self.bottom_controls_layout.addWidget(self.btn_forward, alignment=align_bottom)  # 加快進鈕
        self.bottom_controls_layout.addSpacing(8)  # 插入間距
        self.bottom_controls_layout.addWidget(self.btn_mute, alignment=align_bottom)  # 加靜音鈕
        self.bottom_controls_layout.addWidget(self.vol_slider, alignment=align_bottom)  # 加音量條
        self.bottom_controls_layout.addStretch()  # 彈性伸展
        self.bottom_controls_layout.addWidget(self.btn_screen_layout, alignment=align_bottom)  # 加分屏鈕
        self.bottom_controls_layout.addWidget(self.btn_pip, alignment=align_bottom)  # 加畫畫鈕
        self.bottom_controls_layout.addWidget(self.btn_skin, alignment=align_bottom)  # 加主題鈕
        self.bottom_controls_layout.addWidget(self.btn_hw, alignment=align_bottom)  # 加硬解鈕
        self.bottom_controls_layout.addWidget(self.btn_aspect, alignment=align_bottom)  # 加比例鈕
        self.bottom_controls_layout.addWidget(self.btn_audio, alignment=align_bottom)  # 加音軌鈕
        self.bottom_controls_layout.addWidget(self.btn_sub, alignment=align_bottom)  # 加字幕鈕
        self.bottom_controls_layout.addWidget(self.btn_osd, alignment=align_bottom)  # 加資訊鈕
        self.bottom_controls_layout.addWidget(self.btn_snapshot, alignment=align_bottom)  # 加截圖鈕
        self.bottom_controls_layout.addWidget(self.btn_fullscreen, alignment=align_bottom)  # 加全屏鈕

        bottom_main_layout.addLayout(top_seek_layout)  # 嵌入進度
        bottom_main_layout.addLayout(self.bottom_controls_layout)  # 嵌入按鈕

        # 強制顯示
        self._force_show_all()  # 顯示全部

    def _force_show_all(self):  # 強制顯示
        for btn in [self.btn_screen_layout, self.btn_pip, self.btn_skin,
                    self.btn_hw, self.btn_aspect, self.btn_audio, self.btn_sub,
                    self.btn_snapshot, self.btn_fullscreen]:
            if btn:  # 按鈕存在
                btn.setVisible(True)  # 設為可見
    
    # ----- 控件自適應 -----
    def auto_adjust_controls(self):  # 自動調寬
        if self.main_win.is_pip_mode:  # 畫畫模式
            return  # 直接跳出

        bar_w = self.width()  # 取得寬度
        if bar_w <= 0:  # 寬度無效
            return  # 直接跳出

        spacing = self.bottom_controls_layout.spacing()   # 取得間距
        margin = 16 * 2                                    # 邊框總寬
        min_gap = 5                                        # 最小間距

        # 左側固定寬
        left_need = 64 + 42 + 32 + 32 + 32 + 80   # 組件總寬
        left_need += spacing * 4                   # 間距總寬
        left_need += 8                             # 額外間距

        # 右側固定寬
        right_need = 64 + 64 + spacing             # 右側總寬

        # 中間可隱藏
        middle_items = [  # 中間清單
            self.btn_screen_layout,
            self.btn_pip,
            self.btn_skin,
            self.btn_hw,
            self.btn_aspect,
            self.btn_audio,
            self.btn_sub,
            self.btn_osd,
        ]
        middle_unit = 32 + spacing                   # 單項寬度
        middle_total = 32 * len(middle_items) + spacing * max(0, len(middle_items) - 1)  # 中間總寬

        # 全部所需寬
        total_need = left_need + right_need + middle_total + margin + min_gap  # 計算總寬

        # 空間充足
        if bar_w >= total_need:  # 空間足夠
            for btn in middle_items:  # 遍歷中間
                if btn:  # 按鈕存在
                    btn.setVisible(True)  # 設為顯示
            self.bottom_controls_layout.activate()  # 刷新佈局
            return  # 結束執行

        # 空間不足計算
        available = bar_w - left_need - right_need - margin - min_gap  # 剩餘寬度
        if available < 0:  # 寬度小於0
            available = 0  # 歸零寬度

        # 計算顯示數量
        cumulative = 0  # 累計寬度
        show_map = {}  # 顯示對照
        for i in range(len(middle_items) - 1, -1, -1):  # 反向計算
            w = 32  # 基礎寬度
            if i < len(middle_items) - 1:  # 非首個項
                w += spacing  # 加上間距
            cumulative += w  # 累計寬度
            show_map[i] = cumulative <= available  # 是否容納

        for i, btn in enumerate(middle_items):  # 遍歷中間
            if btn:  # 按鈕存在
                btn.setVisible(show_map.get(i, False))  # 動態顯隱

        # 確保核心顯示
        for btn in [self.play_btn, self.btn_stop, self.btn_rewind,
                    self.btn_forward, self.btn_mute, self.vol_slider,
                    self.btn_snapshot, self.btn_fullscreen]:
            if btn:  # 按鈕存在
                btn.setVisible(True)  # 強制顯示

        self.bottom_controls_layout.activate()  # 刷新佈局
        self.update()  # 重繪元件
    
    # ----- 淡入淡出動畫 -----
    def fade_in(self):  # 淡入動畫
        self.show()  # 顯示元件
        self.setWindowOpacity(0.0)  # 透明度零
        if hasattr(self, '_fade_timer') and self._fade_timer:  # 計時器存在
            self._fade_timer.stop()  # 停止計時
        
        self._fade_step = 0.0  # 步進歸零
        self._fade_timer = QTimer(self)  # 建立計時
        self._fade_timer.setInterval(16)  # 設定幀率
        self._fade_timer.timeout.connect(self._do_fade_in)  # 觸發淡入
        self._fade_timer.start()  # 啟動計時
        self._is_fading = True  # 標記動畫

    def _do_fade_in(self):  # 執行淡入
        self._fade_step += 0.15  # 增加不透明
        if self._fade_step >= 1.0:  # 完全不透明
            self.setWindowOpacity(1.0)  # 設為全顯
            self._fade_timer.stop()  # 停止計時
            self._is_fading = False  # 清除標記
        else:
            self.setWindowOpacity(self._fade_step)  # 套用不透明

    def fade_out(self):  # 淡出動畫
        if self._is_fading:  # 動畫進行中
            return  # 直接跳出
        if hasattr(self, '_fade_timer') and self._fade_timer:  # 計時器存在
            self._fade_timer.stop()  # 停止計時
        
        self._fade_step = self.windowOpacity()  # 取得不透明
        self._fade_timer = QTimer(self)  # 建立計時
        self._fade_timer.setInterval(16)  # 設定幀率
        self._fade_timer.timeout.connect(self._do_fade_out)  # 觸發淡出
        self._fade_timer.start()  # 啟動計時

    def _do_fade_out(self):  # 執行淡出
        self._fade_step -= 0.06  # 減少不透明
        if self._fade_step <= 0.0:  # 完全透明
            self.setWindowOpacity(0.0)  # 設為全隱
            self._fade_timer.stop()  # 停止計時
            self.hide()  # 隱藏組件
        else:
            self.setWindowOpacity(self._fade_step)  # 套用不透明
    
    # ----- 事件處理 -----
    def resizeEvent(self, event):  # 大小變更
        super().resizeEvent(event)  # 呼叫基類
        self.auto_adjust_controls()  # 自動調整

    def enterEvent(self, event):  # 滑鼠進入
        self.main_win.hide_timer.stop()  # 停止倒數
        super().enterEvent(event)  # 呼叫基類

    def leaveEvent(self, event):  # 滑鼠離開
        if self.main_win.isFullScreen():  # 處於全屏
            self.main_win.hide_timer.start()  # 重啟倒數
        super().leaveEvent(event)  # 呼叫基類
# [代碼終點]