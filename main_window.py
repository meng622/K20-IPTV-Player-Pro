from config import * # 載入配置

# 外部模組引用
from pip_manager import PiPManager # 畫中畫
from dialogs import SettingsDialog # 設定視窗
from epg_panel import EPGPanelWidget # 節目表列
from drop_manager import DropManager # 拖放管理
from control_bar import PlayerControlBar # 控制列
from player_engine import MpvEmbedWidget # 播放核心
from screen_manager import ScreenManager # 多屏管理
from skin import IconManager, SkinManager # 主題圖示
from fastcache_manager import FastCache # 播放清單
from hotkey_and_help import HotkeyAndHelpManager # 熱鍵說明
from config import _load_settings, _save_settings # 讀存設定
from m3u_manager import M3U管理主視窗, M3UFetchWorker # M3U解析
from channel_panel import ChannelPanelManager, _clean_epg_key # 頻道清單
from widgets import FlatGradientSlider, CustomSplitter, RoundedMenu # 自訂元件
from epg_manager import EPGDatabase, EPGDownloaderWorker, MemoryEPGWorker, build_epg_lookup # EPG資料

# ==================== K20 主播放器 ====================
# [代碼起點] ...
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QGraphicsOpacityEffect # 主視窗類
# [此處插入新進包]
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QRect # 動畫矩形
from PyQt6.QtGui import QCursor # 全域游標

class K20PlayerUI主視窗(QMainWindow): # 視窗主類
    # -------------------- 初始化 --------------------
    def __init__(self): # 建構函數
        super().__init__() # 父類初始化
        self.setWindowTitle(f"{APP_NAME} (Editor Version) v{APP_VERSION}") # 設定標題
        self.resize(1270, 660) # 設定尺寸

        # 1. 預先宣告所有UI組件與狀態屬性（徹底消滅 hasattr 的根源）
        self.is_seeking = False # 尋道狀態
        self.is_fullscreen_state = False # 全屏狀態
        self.last_layout_count = 1 # 上次分屏
        self.current_layout_count = 1 # 當前分屏
        self.current_url = "" # 當前網址
        self.current_channel_name = "" # 當前頻道
        self.active_player_index = 0 # 聚焦播放
        self.rendered_channel_count = 0 # 渲染數量
        self.current_quality = "全部" # 畫質過濾
        self.current_theme_accent = "" # 主題強調
        self._splitter_initialized = False # 分隔初始化
        
        self.sidebar_btns = [] # 側欄按鈕
        self.filter_btn_list = [] # 過濾按鈕
        self.all_channels_data = [] # 頻道資料
        self.filtered_channels_cache = [] # 快取過濾
        self.history_sources = [] # 歷史紀錄
        self.video_frames = [] # 視訊外框
        self.video_widgets = [] # 視訊元件
        self.epg_cache = {} # 節目快取
        self.current_group_filter = "全部分組" # 當前分組
        self.channel_latencies = {} # 頻道延遲
        self.channel_list_mode = "live" # 列表模式
        self.current_logo_template = "" # 圖標模板
        self.local_media_list = [] # 本地媒體
        self.current_sort_mode = "default" # 排序模式
        self.channels = [] # 頻道列表
        self.epg_data = {} # 節目資料
        self.epg_lookup = {}  # 節目對照
        self.current_channel_obj = {} # 當前頻道
        self.is_m3u_loading = False # 載入標記
        self.is_pip_mode = False # 畫中畫態
        self.current_theme_config = {} # 主題配置
        self.config = {}  # 配置物件

        # UI 控制項屬性統一（全部初始化為 None，後續會由對應方法賦值）
        self.btn_play_pause = None # 播暫按鈕
        self.play_btn = None # 播放按鈕
        self.volume_slider = None # 音量滑軌
        self.vol_slider = None # 音量拉條
        self.seek_slider = None # 進度滑軌
        self.btn_mute = None # 靜音按鈕
        self.btn_hw = None # 硬解按鈕
        self.btn_aspect = None # 比例按鈕
        self.btn_audio = None # 音軌按鈕
        self.btn_osd = None # 資訊按鈕
        self.btn_sub = None # 字幕按鈕
        self.btn_skin = None # 皮膚按鈕
        self.btn_screen_layout = None # 佈局按鈕
        self.btn_epg_toggle = None # 節目開關
        self.video_widget = None # 視訊區域
        self.lbl_current_time = None # 當前時間
        self.lbl_total_time = None # 總共時間

        # 其他可能被查問的屬性
        self.loading_bar = None # 進度條
        self.epg_tip_label = None # 節目提示
        self.tip_label = None # 通用提示
        self.m3u_worker = None # 解析線程
        self._drag_pos = None # 拖拽位置
        self.btn_restore_pip = None # 還原按鈕
        self.sizegrip_pip = None # 縮放手柄
        self.channel_panel = None # 頻道面板
        self.epg_panel = None # 節目面板
        self.channel_list = None # 頻道列表
        self.sidebar = None # 側邊欄
        self.bottom_bar = None # 底部條
        self.player_layout = None # 播放佈局
        self.current_m3u_url = "" # 清單網址
        self.fastcache_mgr = None   # 快取管理
        self._from_cache = False   # 快取標記
        self.is_seeking = False # 尋道標記

#========================================================================

        # 2. 讀取設定檔與初始化 Timer
        self._settings = _load_settings() # 載入設定
        sources = self._settings.get("m3u_sources", []) # 讀取來源
        self.m3u_sources = sources if isinstance(sources, list) else [] # 清單來源
        self.favorites_list = self._settings.get("favorites_list", []) # 我的最愛
        history_data = self._settings.get("history_list", []) or self._settings.get("history_sources", []) # 讀取歷史
        self.history_sources = history_data if isinstance(history_data, list) else [] # 歷史來源
        self.auto_play_last = self._settings.get("auto_play_last", False) # 自動續播
        self.hw_enabled = self._settings.get("hwdec", True) # 硬解開關
        self.cache_mb = self._settings.get("cache_mb", 100) # 快取大小

        saved_url = self._settings.get("current_m3u_url") # 保存網址
        if saved_url: # 若有網址
            self.current_m3u_url = saved_url # 套用網址
        elif self.m3u_sources: # 若有來源
            active_item = next((s for s in self.m3u_sources if isinstance(s, dict) and s.get('active')), self.m3u_sources[0]) # 獲取啟用
            self.current_m3u_url = active_item.get('url', '') if isinstance(active_item, dict) else '' # 取得網址

        # 定時器初始化
        self.hide_timer = QTimer(self) # 隱藏定時
        self.hide_timer.setInterval(3000) # 三秒間隔
        self.hide_timer.timeout.connect(self.hide_fullscreen_bars) # 到期隱藏

        self.ui_timer = QTimer(self) # 界面定時
        self.ui_timer.setInterval(300) # 點三秒間
        self.ui_timer.timeout.connect(self.update_ui_timer) # 定時更新
        self.ui_timer.start() # 啟動定時

        self.seek_debounce_timer = QTimer(self) # 防抖定時
        self.seek_debounce_timer.setSingleShot(True) # 單次觸發
        self.pending_seek_target = None # 預計尋道
        self.seek_debounce_timer.timeout.connect(self._do_real_seek) # 執行尋道

        self.volume_save_timer = QTimer(self) # 音量保存定時
        self.volume_save_timer.setSingleShot(True) # 單次觸發
        self.volume_save_timer.timeout.connect(lambda: _save_settings(self._settings)) # 延遲寫檔

        # 全屏邊緣面板
        self._fs_edge_timer = QTimer(self) # 游標位置監測
        self._fs_edge_timer.setInterval(120) # 120ms
        self._fs_edge_timer.timeout.connect(self._watch_fs_edges) # 監測回呼
        self._fs_hide_timer = QTimer(self) # 離開後延遲隱藏
        self._fs_hide_timer.setSingleShot(True) # 單次
        self._fs_hide_timer.timeout.connect(self._hide_fs_panels) # 隱藏回呼
        self._fs_active = "" # 目前顯示的邊緣面板
        self._fs_epg_was_visible = False # 進入全屏前的 EPG 狀態
        self._fs_channel_was_visible = True # 進入全屏前的頻道面板狀態
        self._fs_saved_sizes = [] # 進入全屏前的分割寬度
        self._fs_anims = {} # 淡入淡出動畫

        # 3. 先建立所有 Manager 實例
        self.skin_mgr = SkinManager(self) # 皮膚管理
        self.channel_mgr = ChannelPanelManager(self) # 頻道管理
        self.screen_mgr = ScreenManager(self) # 螢幕管理
        self.hotkey_help_mgr = HotkeyAndHelpManager(self) # 熱鍵管理
        self.pip_mgr = PiPManager(self) # 畫中畫管
        self.drop_mgr = DropManager(self) # 拖放管理

        # 4. 建立 Layout 結構與 UI 組件
        self.central_widget = QWidget() # 中央元件
        self.setCentralWidget(self.central_widget) # 設定中央
        self.main_layout = QHBoxLayout(self.central_widget) # 主水平列
        self.main_layout.setContentsMargins(0, 0, 0, 0) # 零邊距
        self.main_layout.setSpacing(0) # 零間距

        # 必須先初始化 Hotkey 管理器（供 sidebar 按鈕綁定使用）
        self.shortcut_mgr = self.hotkey_help_mgr # 熱鍵管理器

        # 之後才初始化 sidebar
        self.channel_mgr.init_sidebar() # 初始化側欄

        # 建立中央無級拉伸 Splitter 與頻道面板
        orientation = getattr(Qt.Orientation, 'Horizontal', getattr(Qt, 'Horizontal', None)) # 取得方向
        self.main_splitter = CustomSplitter(orientation, self) # 自訂分隔
        self.main_splitter.setObjectName("main_splitter") # 物件命名
        self.main_splitter.setOpaqueResize(True) # 即時調整
        self.main_splitter.setChildrenCollapsible(False) # 防子折疊
        self.main_splitter.setHandleWidth(3) # 手柄寬度

        # 將 Splitter 拖動信號直接綁定到控制欄調整函數
        self.main_splitter.splitterMoved.connect(lambda pos, index: self._auto_adjust_bottom_controls()) # 移動聯動

        # 直接抓取 Handle 實體物件，強制寫入樣式 (避開 Qt 原生繪製覆蓋)
        handle = self.main_splitter.handle(1) # 取得手柄
        if handle: # 手柄存在
            handle.setStyleSheet("""
                QWidget {
                    background-color: #8b5cf6 !important;
                    border: none !important;
                    image: none !important;
                    border-radius: 3px;
                }
                QWidget:hover {
                    background-color: #00f2fe !important;
                }
                QWidget:pressed {
                    background-color: #38ef7d !important;
                }
            """) # 樣式表

        self.channel_mgr.init_channel_panel() # 頻道面板
        # 現在 channel_panel 已由 channel_mgr 建立，賦值給 self.channel_panel
        
        if self.channel_panel: # 面板存在
            self.channel_panel.setMinimumWidth(300) # 最小寬度
            self.channel_panel.setMaximumWidth(16777215) # 最大寬度
            self.channel_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) # 縮放策略

        # 建立播放區域
        self.init_player_area() # 建播放區

        # 建立右側 EPG 面板
        self.init_epg_panel() # 建節目列

        # 設定 Stretch Factor 權重
        self.main_splitter.setStretchFactor(0, 0) # 左側權重
        self.main_splitter.setStretchFactor(1, 1) # 中間權重
        if self.epg_panel: # 右側存在
            self.main_splitter.setStretchFactor(2, 0) # 右側權重

        self.main_layout.addWidget(self.main_splitter, 0) # 加入分隔

        # 5. 套用主題、加載數據與快捷鍵
        saved_theme = self._settings.get("theme", "purple") # 預設主題
        self.current_theme = saved_theme # 當前主題
        self.skin_mgr.apply_skin(saved_theme) # 套用皮膚

        self.load_initial_channels() # 載入頻道

        if self.auto_play_last: # 自動續播
            last_url = self._settings.get("last_channel_url") # 上次網址
            if last_url: # 網址存在
                self.current_url = last_url # 記錄網址
                self.current_channel_name = self._settings.get("last_channel_name", "上次觀看") # 上次名稱
                self.update_header_title(channel_name=self.current_channel_name) # 更新標題
                QTimer.singleShot(800, lambda: self.video_widget.play(last_url)) # 延遲播放

        # 滑鼠移動監聽
        self.setMouseTracking(True) # 視窗追蹤
        self.central_widget.setMouseTracking(True) # 中央追蹤

        # 啟動時初始化 EPG 資料庫
        self.epg_db = EPGDatabase() # 節目資料

        # 開機時進行一次 UI 狀態校正
        self._update_bottom_control_bar_ui() # 校正底條

        # 玻璃 iOS skin2
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True) # 半透背景

    # -------------------- UI構建 --------------------
    # 創建播放區
    def init_player_area(self): # 建播放區
        player_panel = QWidget() # 播放面板
        player_panel.setObjectName("player_panel") # 物件命名
        player_panel.setMinimumWidth(200) # 最小寬度
        player_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) # 尺寸策略
        player_panel.setStyleSheet("QWidget#player_panel { background-color: #000000; }") # 黑底樣式

        layout = QVBoxLayout(player_panel) # 垂直佈局
        layout.setContentsMargins(0, 0, 0, 0) # 零邊距
        layout.setSpacing(0) # 零間距

        # 頂欄
        self.top_bar = QWidget() # 頂欄元件
        self.top_bar.setObjectName("top_bar") # 物件命名
        self.top_bar.setFixedHeight(50) # 固定高度
        top_layout = QHBoxLayout(self.top_bar) # 水平佈局
        top_layout.setContentsMargins(15, 0, 15, 0) # 左右邊距

        menu_btn = QPushButton("") # 選單按鈕
        menu_btn.setObjectName("btn_menu_toggle") # 物件命名
        menu_btn.setFixedSize(46, 42) # 固定尺寸
        menu_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) # 縮放策略
        menu_btn.setToolTip("開關頻道列表") # 工具提示
        menu_btn.clicked.connect(self.toggle_channel_panel) # 點擊觸發
        self._set_btn_svg_icon(menu_btn, "menu", QSize(36, 36)) # 設定圖示

        self.channel_info = QLabel("[直播流] - 請點擊左側頻道播放") # 資訊標籤
        self.channel_info.setStyleSheet("color: #ccc; font-size: 20px; background: transparent;") # 文字樣式

        self.btn_epg_toggle = QPushButton("節目表") # 節目按鈕
        self.btn_epg_toggle.setObjectName("btn_epg_toggle") # 物件命名
        self.btn_epg_toggle.setCheckable(True) # 切換模式
        self.btn_epg_toggle.setProperty("role", "menu_btn") # 角色屬性
        self.btn_epg_toggle.clicked.connect(self.toggle_epg_panel) # 點擊切換
        self._set_btn_svg_icon(self.btn_epg_toggle, "epg") # 節目圖示
        
        #喺你建立按鈕嘅地方建立刷新按鈕（例如 __init__ 或 setup_ui），加上：
        self.btn_refresh = QPushButton("刷新") # 刷新按鈕
        self.btn_refresh.setObjectName("btn_refresh") # 物件命名
        self.btn_refresh.setProperty("role", "menu_btn") # 角色屬性
        self.btn_refresh.clicked.connect(self.force_refresh_playlist) # 強制刷新
        self._set_btn_svg_icon(self.btn_refresh, "refresh") # 刷新圖示

        top_layout.addWidget(menu_btn) # 加入選單
        top_layout.addSpacing(10) # 增加間隔
        top_layout.addWidget(self.channel_info) # 加入資訊
        top_layout.addStretch() # 伸縮空白
        top_layout.addWidget(self.btn_epg_toggle) # 加入節目
        top_layout.addWidget(self.btn_refresh)   # ← 新加呢行

        # 四屏畫面區域
        self.video_container = QWidget() # 視訊容器
        self.video_container.setStyleSheet("background-color: #000000;") # 純黑背景
        self.grid_layout = QGridLayout(self.video_container) # 網格佈局
        self.grid_layout.setContentsMargins(0, 0, 0, 0) # 零邊距
        self.grid_layout.setSpacing(2) # 畫面間距

        for i in range(4): # 四屏迴圈
            frame = QFrame() # 框架元件
            frame.setFrameShape(QFrame.Shape.NoFrame) # 無邊框架
            frame.setStyleSheet("background-color: #000000;") # 純黑背景

            frame_layout = QVBoxLayout(frame) # 垂直佈局
            frame_layout.setContentsMargins(0, 0, 0, 0) # 零邊距
            frame_layout.setSpacing(0) # 零間距

            # 取得緩存設定（預設 100 MB）
            cache_mb = self.cache_mb # 快取大小
            w = MpvEmbedWidget(cache_mb=cache_mb) # 播放內嵌
            w.hw_enabled = self.hw_enabled # 傳遞硬解
            w.initial_volume = int(self._settings.get("volume", 100)) # 上次音量
            w.requestFullscreenToggle.connect(self.toggle_fullscreen) # 全屏切換
            w.requestShowControls.connect(self._show_controls) # 顯示控制
            w.errorOccurred.connect(self._on_player_error) # 播放錯誤
            w.channelTimeout.connect(self._on_channel_timeout) # 頻道逾時

            frame_layout.addWidget(w) # 放入框架

            frame.installEventFilter(self) # 事件過濾
            w.installEventFilter(self) # 事件過濾

            self.video_frames.append(frame) # 收集框架
            self.video_widgets.append(w) # 收集元件
            w.has_media = False # 媒體標記

        self.video_widget = self.video_widgets[0] # 主播放區

        # 統一主底欄控制條
        self.bottom_bar = PlayerControlBar(self) # 底部控制
        if self.vol_slider: # 音量滑條已建立
            self.vol_slider.blockSignals(True) # 避免啟動時觸發保存
            self.vol_slider.setValue(int(self._settings.get("volume", 100))) # 還原音量
            self.vol_slider.blockSignals(False) # 恢復訊號

        self.player_layout = layout # 佈局引用
        self.player_layout.addWidget(self.top_bar) # 加入頂欄
        self.player_layout.addWidget(self.video_container, stretch=1) # 加入視訊
        self.player_layout.addWidget(self.bottom_bar) # 加入底欄

        self.main_splitter.addWidget(player_panel) # 放入分隔
        player_panel.setMinimumWidth(500) # 最小寬度
        self.screen_mgr.set_screen_layout(1) # 單屏模式

    # 創建EPG面板
    def init_epg_panel(self): # 建節目面板
        self.epg_panel = EPGPanelWidget(self) # 節目元件
        self.main_splitter.addWidget(self.epg_panel) # 加入分隔
        self.epg_panel.setVisible(False) # 預設隱藏

    def _set_btn_svg_icon(self, btn, icon_name, icon_size=None): # 設定圖示
        if icon_size is not None: # 指定尺寸
            btn.setIconSize(icon_size) # 設定尺寸
        cur_size = btn.iconSize() # 獲取尺寸
        if cur_size.width() == 0 or cur_size.height() == 0: # 尺寸為零
            cur_size = QSize(18, 18) # 預設尺寸
            btn.setIconSize(cur_size) # 套用尺寸
        icon = IconManager.get_icon(icon_name, size=cur_size.width()) # 獲取圖示
        btn.setIcon(icon) # 設定圖示

    # 絲滑視窗縮放動畫
    def animate_resize(self, target_w: int, target_h: int, duration: int = 400): # 縮放動畫
        current_geo = self.geometry() # 當前幾何
        target_geo = QRect(current_geo.x(), current_geo.y(), target_w, target_h) # 目標幾何

        self.resize_anim = QPropertyAnimation(self, b"geometry") # 屬性動畫
        self.resize_anim.setDuration(duration) # 動畫時長
        self.resize_anim.setStartValue(current_geo) # 開始位置
        self.resize_anim.setEndValue(target_geo) # 結束位置
        self.resize_anim.setEasingCurve(QEasingCurve.Type.OutQuad) # 緩動曲線
        self.resize_anim.start() # 啟動動畫

    # 自適應底部欄
    def _auto_adjust_bottom_controls(self): # 自適應底欄
        # 避免在 UI 未完整加載前（如 resizeEvent 早於 bottom_bar 創建）訪問屬性而崩潰
        if self.bottom_bar is not None: # 底欄存在
            self.bottom_bar.auto_adjust_controls() # 自動調整

    # 調整分割比例
    def adjust_splitter_ratios(self): # 調整分割
        total_w = self.main_splitter.width() # 總共寬度
        if total_w <= 0: # 無效寬度
            return # 直接返回
        if not self._splitter_initialized: # 未初始化
            self._splitter_initialized = True # 標記已化
            left_w = 240 if self.channel_panel and self.channel_panel.isVisible() else 0 # 左欄寬度
            right_w = 220 if self.epg_panel and self.epg_panel.isVisible() else 0 # 右欄寬度
            if total_w <= 1280: # 小屏調整
                left_w = 200 if left_w > 0 else 0 # 左欄微調
                right_w = 180 if right_w > 0 else 0 # 右欄微調
            center_w = total_w - left_w - right_w # 中間寬度
            sizes = [left_w, center_w] # 比例陣列
            if self.epg_panel and self.epg_panel.isVisible(): # 右欄顯示
                sizes.append(right_w) # 加上右欄
            self.main_splitter.setSizes(sizes) # 套用比例

    # -------------------- 頻道與EPG加載 --------------------
    # 載入初始頻道
    def load_initial_channels(self): # 載初始頻道
        target_url = self._settings.get("current_m3u_url") if isinstance(self._settings, dict) else None # 當前網址
        if not target_url and self.current_m3u_url: # 備用網址
            target_url = self.current_m3u_url # 使用備用
        if not target_url and self.m3u_sources: # 來源網址
            target_url = self.m3u_sources[0]['url'] # 首個來源

        if target_url: # 網址有效
            self.start_parse_m3u(target_url) # 開始解析

    def _get_source_epg_url(self, m3u_url): # 獲取節目網址
        """優先使用該訂閱專屬 EPG，其次才使用舊版全域設定。"""
        for source in self.m3u_sources: # 遍歷來源
            if isinstance(source, dict) and source.get("url") == m3u_url: # 匹配網址
                value = str(source.get("epg") or "").strip() # 取專屬網址
                if value: # 網址存在
                    return value # 返回網址
        if isinstance(self._settings, dict): # 全域設定
            return str(self._settings.get("epg_url", "") or self._settings.get("current_epg_url", "")).strip() # 取全網址
        return "" # 返回空字串

    def _save_current_playlist_cache(self): # 儲存快取
        """只由一個入口寫入快取，避免 M3U 與 EPG 非同步回呼互相覆蓋。"""
        if not self.fastcache_mgr or self._from_cache: # 快取檢查
            return # 跳過儲存
        if not self.all_channels_data: # 空清單不覆蓋舊快取
            print("⚠️ 頻道清單為空，跳過寫入快取") # 保留上一次成功的快取
            return # 結束
        self.fastcache_mgr.channels = list(self.all_channels_data or []) # 同步頻道
        self.fastcache_mgr.epg_data = self.epg_data if isinstance(self.epg_data, dict) else {} # 同步節目
        self.fastcache_mgr._save_parsed_cache() # 寫入檔案
        self.fastcache_mgr._set_last_update_date(date.today()) # 更新日期

    def start_parse_m3u(self, m3u_path_or_url, force_refresh=False): # 開始解析
        """
        載入訂閱；當日有效快取會直接還原，否則才下載並在 EPG 完成後存檔。
        """
        self.current_m3u_url = m3u_path_or_url # 當前路徑
        self._from_cache = False # 快取標記
        if self.search_box: # 換播放列表時清空搜尋
            self.search_box.blockSignals(True) # 避免立即重繪
            self.search_box.clear() # 清空關鍵字
            self.search_box.blockSignals(False) # 恢復訊號
        configured_epg = self._get_source_epg_url(m3u_path_or_url) # 節目網址
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "epg_cache", "playlist_cache") # 快取目錄
        self.fastcache_mgr = FastCache(m3u_path_or_url, configured_epg, cache_dir=cache_dir) # 清單物件

        if not force_refresh and self.fastcache_mgr._is_cache_valid() and self.fastcache_mgr._load_from_parsed_cache(): # 有效快取
            self._from_cache = True # 標記快取
            print("⚡ 已使用有效的 M3U + EPG 本地快取") # 印除錯訊
            QTimer.singleShot(0, lambda: self.on_m3u_parsed(
                self.fastcache_mgr.channels, self.fastcache_mgr.epg_url
            )) # 快取解析
            return # 結束方法

        self.is_m3u_loading = True # 載入標記
        # 先保留舊清單，等下載成功後才替換；失敗時不會變成空白
        if self.loading_bar is not None: # 進度條存在
            self.loading_bar.setRange(0, 100) # 設定範圍
            self.loading_bar.setValue(0) # 歸零進度
            self.loading_bar.setVisible(True) # 顯示進度

        if self.m3u_worker and self.m3u_worker.isRunning(): # 舊線程執行中
            self.m3u_worker.quit() # 停止線程
            self.m3u_worker.wait(1000) # 等待退出

        self.m3u_worker = M3UFetchWorker(m3u_path_or_url) # 新建線程
        self.m3u_worker.finished_signal.connect(self.on_m3u_parsed) # 完成訊號
        self.m3u_worker.progress_signal.connect(self.on_m3u_progress) # 進度訊號
        self.m3u_worker.error_signal.connect(self.on_m3u_error) # 錯誤訊號

        self.m3u_worker.start() # 啟動線程

    # M3U解析進度
    def on_m3u_progress(self, current, total): # 解析進度
        if self.loading_bar is not None and total > 0: # 條件成立
            self.loading_bar.setMaximum(total) # 最大數值
            self.loading_bar.setValue(current) # 當前數值

    # M3U解析錯誤（只提示，不影響既有的 on_m3u_parsed / 快取流程）
    def on_m3u_error(self, message): # 解析錯誤
        print(f"❌ M3U 載入失敗: {message}") # 印錯誤
        if self.isVisible(): # 視窗已顯示
            QMessageBox.warning(self, "M3U 載入失敗", f"無法載入播放列表：\n{message}") # 警告視窗

    # M3U解析完成
    def on_m3u_parsed(self, channels, epg_url, refresh_channels_only=False): # 解析完成
        print("✅ [DEBUG] on_m3u_parsed 被触发了！") # 印除錯訊
        self.is_m3u_loading = False # 載入完成
        if self.loading_bar is not None: # 進度條存在
            self.loading_bar.setVisible(False) # 隱藏進度

        if not isinstance(channels, list) or not channels: # 下載失敗/空清單
            print("⚠️ M3U 解析結果為空，保留舊清單與舊快取") # 不覆蓋
            if self.channel_mgr: # 讓畫面回到舊資料
                self.channel_mgr.load_live_channels(reset=True) # 重新渲染舊清單
            return # 結束，不寫快取

        self.all_channels_data = channels # 更新頻道
        print(f"📦 [DEBUG] M3U 解析完成，收到 {len(channels) if isinstance(channels, list) else 0} 個頻道，EPG 網址: '{epg_url}'") # 除錯訊息

        # ========== 如果係「只更新頻道」，就唔處理 EPG ==========
        if refresh_channels_only: # 僅刷新頻道
            print("🔄 刷新頻道模式：跳過 EPG 處理，保留現有 EPG 數據") # 印訊息
            # 只更新頻道列表
            if self.channel_mgr: # 清單存在
                mgr = self.channel_mgr # 簡寫物件
                mgr.channels = channels # 頻道資料
                mgr.all_channels = channels # 全部頻道
                mgr.load_live_channels(reset=True) # 重置載入
                print("✅ [DEBUG] 已執行 mgr.load_live_channels(reset=True) (刷新模式)") # 印除錯訊
            # 切換到電視直播頁面
            first_btn = self.sidebar_btns[0] if self.sidebar_btns else None # 首個按鈕
            if self.channel_mgr: # 清單存在
                self.channel_mgr.switch_channel_view("live", first_btn) # 切換直播
            return  # 直接返回，唔儲存快取
        
        # ========== 1. 先更新 EPG 數據 ==========
        epg_loaded = False # 節目載入旗標
        if self.fastcache_mgr and self.fastcache_mgr.epg_data: # 有節目快取
            print(f"✅ 使用 playlist_mgr 已快取嘅 EPG 數據，共 {len(self.fastcache_mgr.epg_data)} 個頻道") # 印訊息
            self.epg_data = self.fastcache_mgr.epg_data # 套用節目
            self.epg_lookup = build_epg_lookup(self.epg_data) # 建立索引（含繁簡歸一化變體）
            if self.channel_mgr: # 清單存在
                self.channel_mgr.epg_data = self.epg_data # 同步節目
            if self.epg_panel: # 面板存在
                self.epg_panel.update_epg_content() # 更新內容
            epg_loaded = True # 標記已載

        if not epg_loaded: # 節目未載入
            target_epg_url = self._get_source_epg_url(self.current_m3u_url) or epg_url # 節目網址
            if self.fastcache_mgr: # 快取存在
                self.fastcache_mgr._set_epg_url(target_epg_url) # 設定網址
            if target_epg_url and self.channel_mgr: # 網址有效
                print(f"📡 下載 EPG: {target_epg_url}") # 印下載訊
                self.channel_mgr.load_epg_data(target_epg_url) # 下載節目
            else: # 無網址
                print("⚠️ 沒有 EPG URL，跳過 EPG 載入") # 印跳過訊
                self._save_current_playlist_cache() # 儲存快取

        # ========== 2. 然後先刷新頻道列表（此時 epg_data 已準備好） ==========
        if self.channel_mgr: # 清單存在
            mgr = self.channel_mgr # 簡寫物件
            mgr.channels = channels # 頻道資料
            mgr.all_channels = channels # 全部頻道
            mgr.load_live_channels(reset=True) # 載入直播
            print("✅ [DEBUG] 已執行 mgr.load_live_channels(reset=True)") # 印除錯訊

        # ========== 3. 切換到電視直播頁面 ==========
        first_btn = self.sidebar_btns[0] if self.sidebar_btns else None # 首個按鈕
        if self.channel_mgr: # 清單存在
            self.channel_mgr.switch_channel_view("live", first_btn) # 切換直播

    # 載入EPG數據
    def load_epg(self, epg_url): # 載入節目
        # 如果 playlist_mgr 已經有 epg_data 並且非空，就直接使用
        if self.fastcache_mgr and self.fastcache_mgr.epg_data: # 快取存在
            print(f"✅ 使用已快取嘅 EPG 數據") # 印訊息
            self.epg_data = self.fastcache_mgr.epg_data # 載入快取
            self.on_epg_memory_loaded(self.epg_data) # 完成處理
            return # 跳出方法
        self.setEnabled(False) # 禁用介面

        if self.loading_bar is not None: # 進度條存在
            self.loading_bar.setVisible(True) # 顯示進度
            self.loading_bar.setFixedHeight(50) # 設定高度
            self.loading_bar.setFixedWidth(245) # 設定寬度
            self.loading_bar.setValue(0) # 歸零進度
            self.loading_bar.setFormat(" %p% [%v/%m]") # 格式字串

            if self.epg_tip_label is None: # 提示標籤未建
                self.epg_tip_label = QLabel(self) # 新建標籤
                self.epg_tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # 文字對齊

            # 套用主題顏色
            self.update_dynamic_theme() # 更新主題
            self.epg_tip_label.setText("⏳ 正在加載 EPG 節目標題...\n請耐心等候，\n請勿點擊造成卡頓！\n如果10秒之內都無法加載，\n請完全退出播放器，從新打開。\n如果依然不行，請打任務管理器\n“結束進程”或重啟電腦") # 提示內容
            bar_geo = self.loading_bar.geometry() # 取得位置
            self.epg_tip_label.setGeometry(bar_geo.x() + 50, bar_geo.y() + 65, 270, 380) # 置位置
            self.epg_tip_label.setVisible(True) # 顯示提示
            self.epg_tip_label.raise_() # 移至最上

        QApplication.processEvents() # 刷介面

        self.epg_memory_worker = MemoryEPGWorker(epg_url) # 記憶線程
        self.epg_memory_worker.finished_signal.connect(self.on_epg_memory_loaded) # 完成信號
        self.epg_memory_worker.error_signal.connect(self.on_epg_error) # 失敗信號
        self.epg_memory_worker.start() # 啟動線程
        
    #4️⃣ 新增 force_refresh_playlist 方法，放喺 main_window.py 入面 任何一個 def 之後（例如放喺 load_epg 後面都得），方法內容如下：
    
    def force_refresh_playlist(self): # 強制刷新
        """手動強制更新（直接重新下載）"""
        if not self.current_m3u_url: # 無網址
            print("⚠️ 沒有當前 M3U URL，無法刷新") # 印警告
            return # 跳出方法
        print("🔄 手動強制更新（重新下載 M3U + EPG）...") # 印訊息
        self.start_parse_m3u(self.current_m3u_url, force_refresh=True) # 開始解析
        
    # 動態主題更新
    def update_dynamic_theme(self): # 動態主題
        if self.epg_tip_label is not None: # 標籤存在
            accent = self.current_theme_accent # 強調色彩
            self.epg_tip_label.setStyleSheet(f"""
                color: {accent};
                font-size: 16px;
                font-weight: bold;
                background: rgba(30, 30, 36, 0.9);
                border: 1px solid {accent};
                border-radius: 10px;
                padding: 4px;
            """) # 設定樣式

    # EPG記憶載入
    def on_epg_memory_loaded(self, data): # 記憶加載
        self.epg_data = data # 節目資料
        self.epg_lookup = build_epg_lookup(data) # 節目對照（含繁簡歸一化變體）
        # ===== 新增：將 EPG 數據同步到 channel_mgr =====
        if self.channel_mgr: # 清單存在
            self.channel_mgr.epg_data = data # 同步資料
        # ===== 新增結束 =====
        total_count = len(data) if data else 100 # 總頻道數
        # ... 其餘原有 code 保持不變 ...
        if self.loading_bar is not None: # 進度條存在
            self.loading_bar.setRange(0, total_count) # 進度範圍

        if self.epg_panel: # 節目面板存在
            self.epg_panel.update_epg_content() # 更新內容

        if self.loading_bar is not None: # 進度條存在
            step_chunk = total_count / 10.0 # 步進區塊
            for step in range(1, 6): # 步進迴圈
                self.loading_bar.setValue(int(step_chunk * step)) # 設定進度
                QApplication.processEvents() # 刷介面
                QThread.msleep(20) # 暫停毫秒

        if self.channel_mgr: # 清單存在
            self.channel_mgr.load_live_channels(reset=True) # 載入直播

        if self.loading_bar is not None: # 進度條存在
            for step in range(6, 11): # 後續步進
                self.loading_bar.setValue(int(step_chunk * step)) # 設定進度
                QApplication.processEvents() # 刷介面
                QThread.msleep(20) # 暫停毫秒
                
        self._save_current_playlist_cache() # 儲存快取

        def unlock_ui(): # 解鎖介面
            if self.loading_bar is not None: # 進度條存在
                self.loading_bar.setVisible(False) # 隱藏進度
            if self.epg_tip_label is not None: # 提示存在
                self.epg_tip_label.setVisible(False) # 隱藏提示
            self.setEnabled(True) # 啟用介面
            print(f"✅ 內存 EPG 加載完成，共索引 {len(data)} 個頻道") # 印完成訊

        QTimer.singleShot(200, unlock_ui) # 延遲解鎖
        
    # EPG 單源失敗
    def on_epg_error(self, message): # EPG 失敗
        logging.warning("EPG 載入失敗: %s", message) # 寫入日誌
        if self.channel_info: # 頂欄存在
            self.channel_info.setText(f"EPG 載入失敗：{message}") # 顯示原因

    # EPG下載完成
    def on_epg_download_finished(self, success, msg): # 下載完成
        print(f"EPG 載入狀態: {msg}") # 印載狀態
        if success and self.epg_panel: # 成功且有列
            QTimer.singleShot(500, lambda: self.epg_panel.update_epg_content()) # 延遲更新

    # 更新EPG內容
    def update_epg_content(self, channel_name=None): # 更新內容
        if self.epg_panel: # 面板存在
            self.epg_panel.update_epg_content(channel_name) # 更新節目

    # -------------------- 播放控制 --------------------
    # 播放指定頻道
    def play_channel(self, item, custom_epg="", channel_name=""): # 播指定台
        url = None # 播網址
        ch_name = channel_name # 頻道名
        ch_obj = {} # 頻道物件

        if hasattr(item, 'data'): # 包含資料
            data = item.data(Qt.ItemDataRole.UserRole) # 用戶資料
            ch_obj = item.data(Qt.ItemDataRole.UserRole + 1) or {} # 附加資料
            if isinstance(data, dict): # 字典資料
                url = data.get('url') # 取出網址
                ch_name = data.get('name') or data.get('tvg_name') or data.get('tvg-name') or "" # 取出名稱
                ch_obj = data # 套用字典
            elif isinstance(data, str): # 字串資料
                url = data # 套用網址
        elif isinstance(item, dict): # 字典項目
            url = item.get('url') # 取出網址
            ch_name = item.get('name') or item.get('tvg_name') or item.get('tvg-name') or "" # 取出名稱
            ch_obj = item # 套用字典

        # 1. 備用路徑 A：從 item.text() 嘗試讀取
        if not ch_name and hasattr(item, 'text') and callable(item.text): # 讀取文字
            ch_name = item.text().strip() # 去除空字

        # 2. 備用路徑 B：直擊核心！如果還是拿不到，直接從左側卡片 Widget 的 QLabel 提取頻道名
        if not ch_name and item and self.channel_mgr: # 抓元件字
            try: # 嘗試提取
                w = self.channel_mgr.channel_list.itemWidget(item) # 列表元件
                if w: # 元件存在
                    for lbl in w.findChildren(QLabel): # 找標籤
                        txt = lbl.text().strip() # 標籤內容
                        # 過濾掉 EPG 行（帶 ▶ 的）和數字，剩下的就是頻道名稱
                        if txt and '▶' not in txt and not txt.isdigit(): # 過濾規則
                            ch_name = txt # 取頻道名
                            break # 跳出迴圈
            except Exception: # 忽略例外
                pass # 繼續執行

        if not ch_name: # 無頻道名
            ch_name = "直播頻道" # 預設名稱

        if not url: # 網址為空
            return # 跳出方法

        epg_text = "" # 節目文字
        if isinstance(ch_obj, dict): # 字典物件
            epg_text = ch_obj.get('epg') or ch_obj.get('current_program') or ch_obj.get('epg_title') or "" # 提取節目

        self.current_url = url # 設定網址
        self.current_channel_name = ch_name # 設定名稱
        self.current_channel_obj = ch_obj if isinstance(ch_obj, dict) else {'name': ch_name, 'url': url} # 記錄物件

        self.update_header_title(channel_name=ch_name, custom_epg=custom_epg) # 更新標題

        target_widget = self.get_active_widget() # 獲取窗口

        target_widget.has_media = True # 標記媒體
        target_widget.play(url) # 執行播放
        target_widget.set_volume(int(self._settings.get("volume", 100))) # 套用目前音量

        self._set_btn_svg_icon(self.play_btn, "pause") # 設暫停圖
        QTimer.singleShot(800, lambda: self._set_btn_svg_icon(self.play_btn, "pause")) # 延遲切換

        self.screen_mgr._sync_audio_focus() # 音訊對焦
        QTimer.singleShot(300, self.screen_mgr._sync_audio_focus) # 延遲對焦

        history_item = {'name': ch_name, 'url': url, 'time': int(time.time())} # 歷史物件
        self.history_sources = [h for h in self.history_sources if isinstance(h, dict) and h.get('url') != url] # 移除重複
        self.history_sources.insert(0, history_item) # 插入首位
        self.history_sources = self.history_sources[:100] # 最多百條

        self._settings["history_list"] = self.history_sources # 寫入設定
        self._settings["history_sources"] = self.history_sources # 寫入設定
        self._settings["last_channel_url"] = url # 寫入設定
        self._settings["last_channel_name"] = ch_name # 寫入設定
        _save_settings(self._settings) # 保存設定

        self._set_btn_svg_icon(self.play_btn, "pause") # 切換圖示
        if self.epg_panel and self.epg_panel.isVisible(): # 面板顯示
            self.update_epg_content() # 更新節目

    # 切換播放暫停
    def toggle_play(self): # 切播暫停
        active_w = self.get_active_widget() # 獲取窗口
        if active_w.is_paused: # 處於暫停
            active_w.resume() # 繼續播放
        else: # 處於播放
            active_w.pause() # 暫停播放
            self._update_bottom_control_bar_ui() # 更新底條

    # MPV暫停變更
    def _on_mpv_pause_changed(self, is_paused): # 暫停變更
        icon_name = "play" if is_paused else "pause" # 切換名稱
        if self.play_btn is not None: # 按鈕存在
            self._set_btn_svg_icon(self.play_btn, icon_name) # 套用圖示

    # 停止播放
    def stop_play(self): # 停止播放
        active_w = self.get_active_widget() # 獲取窗口
        if active_w: # 窗口存在
            active_w._set_property_string("time-pos", "0") # 進度歸零
            active_w.pause() # 執行暫停
            self._set_btn_svg_icon(self.play_btn, "play") # 套播圖示
            if self.lbl_current_time: # 時間標籤
                self.lbl_current_time.setText("00:00") # 標籤歸零
            if self.seek_slider: # 進度滑軌
                self.seek_slider.setValue(0) # 滑軌歸零

    # 相對尋道
    def seek_offset(self, offset_sec): # 偏移尋道
        target_player = self.get_active_widget() # 獲取窗口
        if target_player and target_player.mpv: # 核心存在
            target_player.mpv.command("seek", offset_sec, "relative+exact") # 發送尋道

    # 按下進度條
    def on_seek_pressed(self): # 按下尋道
        self.is_seeking = True # 尋道標記

    # 釋放進度條
    def on_seek_released(self): # 釋放尋道
        val = self.seek_slider.value() if self.seek_slider else 0 # 獲取滑軌
        target_player = self.get_active_widget() # 獲取窗口

        duration = target_player.get_duration() # 總共時長

        if duration > 0: # 時長有效
            target_pos = (val / 1000.0) * duration # 計算目標
            self.pending_seek_target = target_pos # 記錄目標
            self.seek_debounce_timer.start(300) # 啟動防抖

        self.is_seeking = False # 解除標記

    def _do_real_seek(self): # 執行尋道
        if self.pending_seek_target is not None: # 目標存在
            target_player = self.get_active_widget() # 獲取窗口
            if target_player and target_player.mpv: # 核心存在
                target_player.mpv.command('seek', self.pending_seek_target, 'absolute') # 絕對尋道
            self.pending_seek_target = None # 重置目標

    # 播放器錯誤
    def _on_player_error(self, message): # 播放錯誤
        logging.error("播放器錯誤: %s", message) # 寫入日誌
        if self.channel_info: # 頂欄存在
            self.channel_info.setText(f"播放錯誤：{message}") # 顯示原因

    # 頻道逾時
    def _on_channel_timeout(self, url): # 頻道逾時
        logging.warning("頻道連線逾時: %s", url) # 寫入日誌

    # 設置音量
    def set_volume(self, value): # 設定音量
        active_w = self.get_active_widget() # 獲取窗口
        if not active_w: # 窗口為空
            return # 跳出方法
        active_w.set_volume(value) # 調整音量
        is_muted = active_w.get_mute() # 靜音狀態
        if self.btn_mute: # 按鈕存在
            self._set_btn_svg_icon(self.btn_mute, "mute" if (value == 0 or is_muted) else "volume") # 更新圖示
        self._settings["volume"] = int(value) # 記住音量
        if hasattr(self, "volume_save_timer"): # 延遲寫檔
            self.volume_save_timer.start(600) # 600ms 防抖

    # 切換靜音
    def toggle_mute(self): # 切換靜音
        active_w = self.get_active_widget() # 獲取窗口
        if not active_w: # 窗口為空
            return # 跳出方法
        current_mute = active_w.get_mute() # 當前靜音
        active_w.set_mute(not current_mute) # 反轉靜音
        self.sync_controls_ui() # 同步介面

    # 獲取當前活動窗口
    def get_active_widget(self): # 獲取焦點
        if self.video_widgets and 0 <= self.active_player_index < len(self.video_widgets): # 索引有效
            return self.video_widgets[self.active_player_index] # 返回焦點
        return self.video_widget # 預設窗口

    # 更新底部控制欄UI
    def _update_bottom_control_bar_ui(self): # 更新底欄
        active_w = self.get_active_widget() # 獲取窗口
        if not active_w: # 窗口為空
            return # 跳出方法
        try: # 嘗試更新
            is_paused = active_w.is_paused # 暫停狀態
            icon_name = "play" if is_paused else "pause" # 圖示名稱
            if self.play_btn: # 按鈕存在
                self.play_btn.setText("") # 清空文字
                self._set_btn_svg_icon(self.play_btn, icon_name) # 設定圖示
            cur_vol = active_w.get_volume() # 當前音量
            if self.vol_slider: # 滑軌存在
                self.vol_slider.blockSignals(True) # 阻斷信號
                self.vol_slider.setValue(int(cur_vol if cur_vol is not None else 100)) # 設定數值
                self.vol_slider.blockSignals(False) # 解開信號
        except Exception: # 捕捉例外
            pass # 忽略錯誤

    # 更新頂部標題
    def update_header_title(self, channel_name=None, custom_title=None, custom_epg=None): # 更新標題
        if channel_name: # 頻道名稱
            self.current_channel_name = channel_name # 保存名稱
            epg_clean = custom_epg.strip() if custom_epg else "" # 整理節目
            if epg_clean: # 節目非空
                if not epg_clean.startswith('▶'): # 前綴檢查
                    epg_clean = f"▶{epg_clean}" # 加上箭頭
                display_str = f"[直播流] - {channel_name} - {epg_clean}" # 組合字串
            else: # 無節目訊
                display_str = f"[直播流] - {channel_name} - 無節目資訊" # 預設字串
        elif custom_title: # 自訂標題
            display_str = str(custom_title) # 轉為字串
        else: # 無資訊態
            display_str = "[無播放資訊]" # 預設標題
        self.channel_info.setText(display_str) # 設定標籤
        self.setWindowTitle(f"{APP_NAME} (Editor Version) v{APP_VERSION} - {display_str}") # 設定視窗

    # 同步控制UI
    def sync_controls_ui(self): # 同步介面
        self._update_bottom_control_bar_ui() # 更新底欄
        active_w = self.get_active_widget() # 獲取窗口
        if not active_w: # 窗口為空
            return # 跳出方法
        is_muted = active_w.get_mute() # 靜音狀態
        vol = active_w.get_volume() # 當前音量
        if self.vol_slider: # 滑軌存在
            self.vol_slider.blockSignals(True) # 封鎖信號
            self.vol_slider.setValue(int(vol)) # 套用數值
            self.vol_slider.blockSignals(False) # 解封信號
        if self.btn_mute: # 按鈕存在
            self._set_btn_svg_icon(self.btn_mute, "mute" if (is_muted or vol == 0) else "volume") # 更新圖示

    # 定時更新UI
    def update_ui_timer(self): # 定時更新
        active_w = self.get_active_widget() # 獲取窗口
        if not active_w or not active_w.mpv: # 核心無效
            return # 跳出方法
        try: # 嘗試更新
            duration = active_w.get_duration() # 總共時長
            pos = active_w.get_time_pos() # 當前位置
            if duration and duration > 0: # 時長有效
                if not self.is_seeking and self.seek_slider: # 非尋道中
                    self.seek_slider.setValue(int((pos / duration) * 1000)) # 更新滑軌
                if self.lbl_current_time: # 當前時間
                    self.lbl_current_time.setText(self.format_time(int(pos * 1000))) # 套用時間
                if self.lbl_total_time: # 總共時間
                    self.lbl_total_time.setText(self.format_time(int(duration * 1000))) # 套用總時
                if self.seek_slider: # 滑軌存在
                    self.seek_slider.setEnabled(True) # 啟用滑軌
            else: # 無效時長
                if self.lbl_current_time: # 時間標籤
                    self.lbl_current_time.setText("00:00") # 歸零時間
                if self.lbl_total_time: # 總時標籤
                    self.lbl_total_time.setText("00:00") # 歸零總時
                if self.seek_slider: # 滑軌存在
                    self.seek_slider.setValue(0) # 歸零滑軌
                    self.seek_slider.setEnabled(False) # 禁用滑軌
            self._update_bottom_control_bar_ui() # 更新底欄
        except Exception: # 捕捉例外
            pass # 忽略錯誤

    # 顯示OSD
    def show_osd(self): # 顯示資訊
        if self.video_widgets: # 視訊存在
            self.video_widgets[0].mpv.toggle_stats() # 切換統計

    # -------------------- 全屏與面板切換 --------------------
    # 切換全屏
    def toggle_fullscreen(self): # 切換全屏
        if self.pip_mgr and self.pip_mgr.is_pip_mode: # 畫中畫中
            return # 跳出方法
        if self.isFullScreen(): # 處於全屏
            self._fs_edge_timer.stop() # 停止邊緣監測
            self._fs_hide_timer.stop() # 停止隱藏倒數
            self._fs_active = "" # 清除狀態
            if self.epg_panel: # 節目表存在
                self._fs_force_visible(self.epg_panel, self._fs_epg_was_visible) # 還原進入前狀態
            if self.bottom_bar: # 底欄存在
                self.bottom_bar.clearMask() # 清除遮罩
                self.bottom_bar.setWindowFlags(Qt.WindowType.Widget) # 標記元件
                self.bottom_bar.setMinimumSize(0, 0) # 最小尺寸
                self.bottom_bar.setMaximumSize(16777215, 16777215) # 最大尺寸
                self.bottom_bar.setFixedHeight(100) # 固定高度
                self.bottom_bar.setStyleSheet("") # 清除樣式
                self.bottom_bar.setObjectName("bottom_bar") # 物件命名
            self.showNormal() # 視窗還原
            if self.sidebar is not None: # 側欄存在
                self._fs_force_visible(self.sidebar, True) # 顯示並還原透明度
            if self.channel_panel is not None: # 面板存在
                self._fs_force_visible(self.channel_panel, self._fs_channel_was_visible) # 還原進入前狀態
            if self.top_bar: # 頂欄存在
                self._fs_force_visible(self.top_bar, True) # 顯示並還原透明度
            if self.bottom_bar: # 底欄存在
                self.bottom_bar.setVisible(True) # 顯示底欄
            if self.player_layout is not None and self.bottom_bar: # 佈局存在
                self.bottom_bar.setParent(None) # 移出父項
                self.player_layout.addWidget(self.bottom_bar) # 加回佈局
            self.hide_timer.stop() # 停止定時
            self.unsetCursor() # 還原游標
            if self._fs_saved_sizes: # 還原原本寬度
                QTimer.singleShot(0, lambda: self.main_splitter.setSizes(self._fs_saved_sizes)) # 延遲套用
        else: # 處於視窗
            self._fs_epg_was_visible = bool(self.epg_panel and self.epg_panel.isVisible()) # 記住 EPG 狀態
            self._fs_channel_was_visible = bool(self.channel_panel and self.channel_panel.isVisible()) # 記住頻道面板
            self._fs_saved_sizes = list(self.main_splitter.sizes()) if self.main_splitter else [] # 記住寬度
            self._fs_active = "" # 清除邊緣狀態
            if self.sidebar is not None: # 側欄存在
                self.sidebar.setVisible(False) # 隱藏側欄
            if self.channel_panel is not None: # 面板存在
                self.channel_panel.setVisible(False) # 隱藏面板
            if self.epg_panel: # 節目表存在
                self.epg_panel.setVisible(False) # 全屏先收起
            if self.top_bar: # 頂欄存在
                self.top_bar.setVisible(False) # 隱藏頂欄
            if self.bottom_bar: # 底欄存在
                self.bottom_bar.setParent(None) # 移出父項
                self.bottom_bar.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint) # 置頂提示
                self.bottom_bar.hide() # 隱藏底欄
            self.showFullScreen() # 進入全屏
            self.hide_timer.start() # 啟動定時
            self._fs_edge_timer.start() # 啟動邊緣監測
        current = getattr(self, 'current_theme', 'purple') # 當前主題
        self.skin_mgr.apply_skin(current) # 套用皮膚

    # 顯示全屏控制欄
    def _show_controls(self): # 顯示控制
        if self.isFullScreen(): # 處於全屏
            if self.bottom_bar and self.bottom_bar.isVisible() and self.bottom_bar.windowOpacity() >= 0.99: # 控制顯示
                self.hide_timer.start() # 啟動定時
                return # 跳出方法
            MARGIN_X = 40 # 橫向邊距
            screen_geom = self.screen().geometry() # 螢幕幾何
            vw = screen_geom.width() - (MARGIN_X * 2) # 計算寬度
            bh = 100 # 控制高度
            OFFSET_Y = 30 # 縱向偏移
            target_x = screen_geom.x() + MARGIN_X # 目標橫座標
            target_y = screen_geom.y() + screen_geom.height() - bh - OFFSET_Y # 目標縱座標
            if self.bottom_bar: # 底欄存在
                self.bottom_bar.setFixedSize(vw, bh) # 固定尺寸
                self.bottom_bar.setGeometry(target_x, target_y, vw, bh) # 設定幾何
                path = QPainterPath() # 繪製路徑
                path.addRoundedRect(QRectF(0, 0, vw, bh), 12, 12) # 圓角矩形
                self.bottom_bar.setMask(QRegion(path.toFillPolygon().toPolygon())) # 設定遮罩
                self.bottom_bar.fade_in() # 淡入效果
                self.bottom_bar.raise_() # 移至最上
            self.unsetCursor() # 顯示游標
            self.hide_timer.start() # 重設定時

    # 隱藏全屏控制欄
    def hide_fullscreen_bars(self): # 隱藏控制
        if self.isFullScreen(): # 處於全屏
            if self.bottom_bar and getattr(self.bottom_bar, '_is_fading', False): # 淡化中
                self.hide_timer.start() # 重設定時
                return # 跳出方法
            if self.bottom_bar: # 底欄存在
                self.bottom_bar.fade_out() # 淡出效果
            if self.top_bar and self._fs_active != "right": # 右緣面板使用中
                self.top_bar.hide() # 隱藏頂欄
            if not self._fs_active: # 沒有邊緣面板
                self.setCursor(Qt.CursorShape.BlankCursor) # 隱藏游標

    # -------------------- 全屏邊緣面板 --------------------
    def _watch_fs_edges(self): # 監測全屏邊緣
        if not self.isFullScreen(): # 非全屏
            return # 結束
        if QApplication.mouseButtons() & Qt.MouseButton.LeftButton: # 正在拖動分割條
            self._fs_hide_timer.stop() # 不要淡出
            return # 結束
        pos = QCursor.pos() # 全域游標
        geo = self.screen().geometry() # 螢幕範圍
        margin = 5 # 邊緣感應寬度
        near_left = pos.x() <= geo.left() + margin # 左緣
        near_right = pos.x() >= geo.right() - margin # 右緣
        if near_left: # 左緣
            self._show_fs_left() # 顯示左側頻道
        elif near_right: # 右緣
            self._show_fs_right() # 顯示標題欄+節目表
        if self._fs_active and not self._fs_contains(pos) and not (near_left or near_right): # 離開面板
            if not self._fs_hide_timer.isActive(): # 尚未倒數
                self._fs_hide_timer.start(600) # 600ms 後淡出，留時間拖分割條
        else: # 還在面板/邊緣
            self._fs_hide_timer.stop() # 取消隱藏

    def _fs_contains(self, pos): # 游標是否在面板內
        for widget in (self.sidebar, self.channel_panel, self.epg_panel, self.top_bar): # 所有面板
            if widget and widget.isVisible(): # 可見
                top_left = widget.mapToGlobal(QPoint(0, 0)) # 全域左上
                if QRect(top_left, widget.size()).contains(pos): # 命中
                    return True # 在面板內
        return False # 不在

    def _show_fs_left(self): # 顯示左側頻道
        if self._fs_active == "left": # 已顯示
            self._fs_hide_timer.stop() # 取消隱藏
            return # 結束
        self._fs_active = "left" # 記錄
        self.unsetCursor() # 顯示游標
        self._fs_show(self.top_bar, False) # 收起上欄
        self._fs_show(self.epg_panel, False) # 收起節目表
        self._fs_show(self.sidebar, True) # 顯示側欄
        self._fs_show(self.channel_panel, True) # 顯示頻道
        self._fs_resize_splitter() # 重算寬度

    def _show_fs_right(self): # 顯示右側節目表
        if self._fs_active == "right": # 已顯示
            self._fs_hide_timer.stop() # 取消隱藏
            return # 結束
        self._fs_active = "right" # 記錄
        self.unsetCursor() # 顯示游標
        self._fs_show(self.sidebar, False) # 收起側欄
        self._fs_show(self.channel_panel, False) # 收起頻道
        self._fs_show(self.top_bar, True) # 顯示標題欄
        self._fs_show(self.epg_panel, True) # 顯示節目表
        self._fs_resize_splitter() # 重算寬度

    def _hide_fs_panels(self): # 收起邊緣面板
        if not self.isFullScreen(): # 非全屏
            return # 結束
        self._fs_active = "" # 清除狀態
        for widget in (self.sidebar, self.channel_panel, self.epg_panel, self.top_bar): # 所有面板
            self._fs_show(widget, False) # 淡出
        self._fs_resize_splitter() # 重算寬度

    def _fs_resize_splitter(self): # 全屏分割寬度
        if not self.main_splitter: # 無分割器
            return # 結束
        total = self.main_splitter.width() # 總寬
        if total <= 0: # 尚未佈局
            return # 結束
        left = max(320, min(380, total // 5)) if self.channel_panel and self.channel_panel.isVisible() else 0 # 左寬
        right = max(340, min(400, total // 5)) if self.epg_panel and self.epg_panel.isVisible() else 0 # 右寬
        center = max(320, total - left - right) # 中間
        sizes = [left, center] # 左+中
        if self.epg_panel: # 有右欄
            sizes.append(right) # 加右欄
        self.main_splitter.setSizes(sizes) # 套用

    def _fs_show(self, widget, show): # 淡入/淡出
        if not widget: # 無控件
            return # 結束
        key = id(widget) # 動畫鍵
        old = self._fs_anims.pop(key, None) # 舊動畫
        if old: # 有舊動畫
            old.stop() # 停止
        effect = widget.graphicsEffect() # 透明度效果
        if not isinstance(effect, QGraphicsOpacityEffect): # 尚未建立
            effect = QGraphicsOpacityEffect(widget) # 建立效果
            widget.setGraphicsEffect(effect) # 綁定
        if show: # 淡入
            widget.show() # 先顯示
            effect.setOpacity(0.0) # 從 0 開始
            anim = QPropertyAnimation(effect, b"opacity", self) # 動畫
            anim.setDuration(160) # 時長
            anim.setStartValue(0.0) # 起點
            anim.setEndValue(1.0) # 終點
            anim.start() # 啟動
            self._fs_anims[key] = anim # 保留引用
        else: # 淡出
            if not widget.isVisible(): # 已隱藏
                effect.setOpacity(1.0) # 還原
                return # 結束
            anim = QPropertyAnimation(effect, b"opacity", self) # 動畫
            anim.setDuration(160) # 時長
            anim.setStartValue(effect.opacity()) # 目前
            anim.setEndValue(0.0) # 終點
            anim.finished.connect(lambda w=widget, k=key, a=anim: self._fs_hide_done(w, k, a)) # 完成後隱藏
            anim.start() # 啟動
            self._fs_anims[key] = anim # 保留引用

    def _fs_hide_done(self, widget, key, anim): # 淡出完成
        if self._fs_anims.get(key) is not anim: # 已被新動畫取代
            return # 結束
        self._fs_anims.pop(key, None) # 移除
        widget.hide() # 隱藏
        effect = widget.graphicsEffect() # 效果
        if isinstance(effect, QGraphicsOpacityEffect): # 是透明度
            effect.setOpacity(1.0) # 還原，下次顯示用

    def _fs_force_visible(self, widget, visible): # 強制顯示/隱藏（離開全屏用）
        if not widget: # 無控件
            return # 結束
        key = id(widget) # 動畫鍵
        old = self._fs_anims.pop(key, None) # 舊動畫
        if old: # 停止
            old.stop() # 停止
        effect = widget.graphicsEffect() # 效果
        if isinstance(effect, QGraphicsOpacityEffect): # 還原透明度
            effect.setOpacity(1.0) # 全不透明
        widget.setVisible(visible) # 顯示/隱藏

    # 切換頻道面板
    def toggle_channel_panel(self): # 切換面板
        if self.channel_panel is None: # 面板為空
            return # 跳出方法
        is_visible = self.channel_panel.isVisible() # 顯示狀態
        self.channel_panel.setVisible(not is_visible) # 反轉顯示
        self.adjust_splitter_ratios() # 調整比例
        QTimer.singleShot(20, self._auto_adjust_bottom_controls) # 延遲調整

    # 切換EPG面板
    def toggle_epg_panel(self): # 切節目表
        if self.epg_panel: # 面板存在
            self.epg_panel.toggle_panel() # 切換面板
            if self.isFullScreen(): # 全屏時重算寬度
                QTimer.singleShot(0, self._fs_resize_splitter) # 延遲套用

    # 切換畫中畫
    def toggle_pip(self): # 切畫中畫
        self.pip_mgr.toggle() # 切換狀態

    # -------------------- 菜單與樣式 --------------------
    # 皮膚菜單
    def show_skin_menu(self): # 皮膚選單
        menu = RoundedMenu(self) # 圓角選單
        menu.addAction("暗黑魅紫 (Default)", lambda: self.skin_mgr.apply_skin("purple")) # 紫色主題
        menu.addAction("賽博霓藍", lambda: self.skin_mgr.apply_skin("cyan")) # 藍色主題
        menu.addAction("翡翠極光", lambda: self.skin_mgr.apply_skin("emerald")) # 綠色主題
        menu.addAction("鈦空深灰", lambda: self.skin_mgr.apply_skin("slate")) # 灰色主題
        if self.btn_skin: # 按鈕存在
            menu.exec(self.btn_skin.mapToGlobal(QPoint(0, self.btn_skin.height()))) # 彈出選單

    # 佈局菜單
    def show_screen_layout_menu(self): # 佈局選單
        menu = RoundedMenu(self) # 圓角選單
        menu.addAction("單屏模式 (標準)", lambda: self.screen_mgr.set_screen_layout(1)) # 單屏選項
        menu.addAction("雙屏模式 (左右)", lambda: self.screen_mgr.set_screen_layout(2)) # 雙屏選項
        menu.addAction("三屏模式 (1:2)", lambda: self.screen_mgr.set_screen_layout(3)) # 三屏選項
        menu.addAction("四屏模式 (田字)", lambda: self.screen_mgr.set_screen_layout(4)) # 四屏選項
        if self.btn_screen_layout: # 按鈕存在
            menu.exec(self.btn_screen_layout.mapToGlobal(QPoint(0, self.btn_screen_layout.height()))) # 彈出選單

    # 寬高比菜單
    def show_aspect_menu(self): # 比例選單
        menu = RoundedMenu(self) # 圓角選單
        active_w = self.get_active_widget() # 獲取窗口
        ratios = [ # 比例選項
            ("預設 (原始)", None),
            ("16:10", 16 / 10),
            ("18:9", 18 / 9),
            ("21:9", 21 / 9),
            ("16:9", 16 / 9),
            ("4:3", 4 / 3),
            ("1:1", 1 / 1),
            ("填滿畫面", "fill")
        ]
        for label, ratio in ratios: # 遍歷選項
            action = QAction(label, self) # 建立動作
            action.triggered.connect(lambda _, r=ratio, w=active_w: w.set_aspect(r)) # 綁定動作
            menu.addAction(action) # 加入選單
        if self.btn_aspect: # 按鈕存在
            menu.exec(self.btn_aspect.mapToGlobal(self.btn_aspect.rect().bottomLeft())) # 彈出選單

    # 音軌菜單
    def show_audio_menu(self): # 音軌選單
        menu = RoundedMenu(self) # 圓角選單
        active_w = self.get_active_widget() # 獲取窗口
        track_json = active_w.get_property_string("track-list") # 獲取音軌
        current_aid = active_w.get_property_string("aid") or "no" # 當前音軌
        if not track_json: # 無音軌軌
            menu.addAction(QAction("無可用音軌", self)) # 提示動作
            if self.btn_audio: # 按鈕存在
                menu.exec(self.btn_audio.mapToGlobal(self.btn_audio.rect().bottomLeft())) # 彈出選單
            return # 跳出方法
        try: # 嘗試解析
            tracks = json.loads(track_json) # 解析清單
            audio_tracks = [t for t in tracks if t.get("type") == "audio"] # 過濾音軌
            if not audio_tracks: # 無音軌軌
                menu.addAction(QAction("無可用音軌", self)) # 提示動作
            else: # 有可用軌
                seen_langs = set() # 已見語言
                for t in audio_tracks: # 遍歷音軌
                    tid = str(t.get("id", "")) # 音軌編號
                    raw_title = t.get("title", "") or t.get("lang", "") or f"音軌 {tid}" # 原始標題
                    clean_title = raw_title # 乾淨標題
                    if "audio only" in raw_title: # 淨純音軌
                        if "(" in raw_title and ")" in raw_title: # 包含括號
                            clean_title = raw_title[raw_title.find("(")+1:raw_title.rfind(")")] # 截取名稱
                    if clean_title in seen_langs: # 重複語言
                        continue # 跳過重複
                    seen_langs.add(clean_title) # 記錄語言
                    label = f"{'✅ ' if tid == current_aid else ''}{clean_title}" # 標籤文本
                    action = QAction(label, self) # 建立動作
                    action.triggered.connect(lambda _, id=tid, w=active_w: w._set_property_string("aid", id)) # 綁定音軌
                    menu.addAction(action) # 加入選單
        except Exception: # 解析失敗
            menu.addAction(QAction("無可用音軌", self)) # 提示動作
        if self.btn_audio: # 按鈕存在
            menu.exec(self.btn_audio.mapToGlobal(self.btn_audio.rect().bottomLeft())) # 彈出選單

    # 字幕菜單
    def show_subtitle_menu(self): # 字幕選單
        menu = RoundedMenu(self) # 圓角選單
        active_w = self.get_active_widget() # 獲取窗口
        track_json = active_w.get_property_string("track-list") # 獲取軌道
        current_sid = active_w.get_property_string("sid") or "no" # 當前字幕
        if not track_json: # 無軌道檔
            menu.addAction(QAction("無可用字幕", self)) # 提示動作
            if self.btn_sub: # 按鈕存在
                menu.exec(self.btn_sub.mapToGlobal(self.btn_sub.rect().bottomLeft())) # 彈出選單
            return # 跳出方法
        try: # 嘗試解析
            tracks = json.loads(track_json) # 解析 JSON
            sub_tracks = [t for t in tracks if t.get("type") == "sub"] # 過濾字幕
            if not sub_tracks: # 無字幕軌
                menu.addAction(QAction("無可用字幕", self)) # 提示動作
            else: # 有字幕軌
                for t in sub_tracks: # 遍歷字幕
                    tid = str(t.get("id", "")) # 字幕編號
                    ttitle = t.get("title", "") or t.get("lang", "") or f"字幕 {tid}" # 字幕標題
                    label = f"{'✅ ' if tid == current_sid else ''}{ttitle}" # 標籤字串
                    action = QAction(label, self) # 建立動作
                    action.triggered.connect(lambda _, id=tid, w=active_w: w._set_property_string("sid", id)) # 切換字幕
                    menu.addAction(action) # 加入選單
                menu.addSeparator() # 分隔線條
                off = QAction("❌ 關閉字幕", self) # 關閉動作
                off.triggered.connect(lambda checked=False, w=active_w: w._set_property_string("sid", "no")) # 關閉字幕
                menu.addAction(off) # 加入選單
        except Exception: # 捕捉例外
            menu.addAction(QAction("無可用字幕", self)) # 提示動作
        if self.btn_sub: # 按鈕存在
            menu.exec(self.btn_sub.mapToGlobal(self.btn_sub.rect().bottomLeft())) # 彈出選單

    # 更新側邊欄樣式
    def update_sidebar_btn_styles(self, active_btn): # 側欄樣式
        self.current_sidebar_btn = active_btn # 當前按鈕
        accent = self.current_theme_accent # 主題顏色
        for btn in self.sidebar_btns: # 遍歷按鈕
            icon_name = btn.property("icon_name") # 圖示名稱
            is_active = (btn == active_btn) # 是否啟用
            btn.setProperty("active", is_active) # 設定屬性
            btn.style().unpolish(btn) # 刷新樣式
            btn.style().polish(btn) # 重繪樣式
            if icon_name: # 圖示存在
                color = accent if is_active else "#FFFFFF" # 色彩選擇
                icon = IconManager.get_icon(icon_name, color=color, size=22) # 讀取圖示
                btn.setIcon(icon) # 設定圖示

    # 更新硬件加速按鈕
    def _update_hw_btn_style(self): # 硬解樣式
        accent = self.current_theme_accent # 主題色彩
        if self.hw_enabled: # 硬解開啟
            self.btn_hw.setStyleSheet(f"""
                QPushButton {{
                    background-color: {accent} !important;
                    border: 1px solid {accent} !important;
                    border-radius: 12px !important;
                }}
            """) # 開啟樣式
            self.btn_hw.setToolTip("HW: On") # 工具提示
        else: # 硬解關閉
            self.btn_hw.setStyleSheet("") # 清除樣式
            self.btn_hw.setToolTip("HW: Off") # 工具提示
        self.btn_hw.style().unpolish(self.btn_hw) # 刷新樣式
        self.btn_hw.style().polish(self.btn_hw) # 重繪樣式
        self.btn_hw.update() # 更新按鈕

    # -------------------- 事件處理 --------------------
    # 事件過濾器
    def eventFilter(self, watched, event): # 事件過濾
        if watched == self.video_widget and self.is_pip_mode: # 畫中畫中
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton: # 按下左鍵
                pos = event.pos() # 點擊位置
                btn_hit = (self.btn_restore_pip is not None and self.btn_restore_pip.isVisible() and self.btn_restore_pip.geometry().contains(pos)) # 還原按鈕
                grip_hit = (self.sizegrip_pip is not None and self.sizegrip_pip.isVisible() and self.sizegrip_pip.geometry().contains(pos)) # 縮放手柄
                if not btn_hit and not grip_hit: # 點擊空白
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft() # 計算位置
                    return True # 攔截事件
            elif event.type() == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton: # 拖曳視窗
                if self._drag_pos is not None: # 位置有效
                    self.move(event.globalPosition().toPoint() - self._drag_pos) # 移動視窗
                    return True # 攔截事件
            elif event.type() == QEvent.Type.MouseButtonRelease: # 放開左鍵
                self._drag_pos = None # 清空位置
        return super().eventFilter(watched, event) # 父類處理

    # 鼠標移動事件
    def mouseMoveEvent(self, event): # 滑鼠移動
        if self.isFullScreen(): # 全屏狀態
            if self.bottom_bar and self.bottom_bar.isVisible() and self.bottom_bar.windowOpacity() >= 0.99: # 顯示底欄
                self.hide_timer.start() # 啟動定時
            else: # 底欄隱藏
                self._show_controls() # 顯示控制
        super().mouseMoveEvent(event) # 父類事件

    # 窗口尺寸變化
    def resizeEvent(self, event): # 縮放事件
        super().resizeEvent(event) # 父類處理
        self._auto_adjust_bottom_controls() # 調整底欄

    # 窗口顯示事件
    def showEvent(self, event): # 顯示事件
        super().showEvent(event) # 父類處理
        QTimer.singleShot(50, self._auto_adjust_bottom_controls) # 延遲調整
        if (getattr(self, "pip_mgr", None) and self.pip_mgr.is_pip_mode
                and not getattr(self.pip_mgr, "_entering", False)): # 可能在任務欄還原
            QTimer.singleShot(0, self._exit_pip_from_taskbar) # 延遲確認

    # 視窗狀態變化（含從任務欄還原）
    def changeEvent(self, event): # 狀態變化
        super().changeEvent(event) # 父類處理
        if event.type() != QEvent.Type.WindowStateChange: # 只處理狀態
            return # 結束
        if not getattr(self, "pip_mgr", None) or not self.pip_mgr.is_pip_mode: # 非 PiP
            return # 結束
        if getattr(self.pip_mgr, "_entering", False): # 正在進入 PiP
            return # 結束
        QTimer.singleShot(80, self._exit_pip_from_taskbar) # 等狀態穩定後確認

    def _exit_pip_from_taskbar(self): # 任務欄還原
        if not getattr(self, "pip_mgr", None) or not self.pip_mgr.is_pip_mode: # 已退出
            return # 結束
        if not self.isVisible() or self.isMinimized() or self.isFullScreen(): # 仍在最小化/隱藏
            return # 不處理
        self.pip_mgr.exit_pip() # 恢復主視窗

    # ESC鍵處理
    def _esc_handler(self): # 按鍵處理
        if self.isFullScreen(): # 處於全屏
            self.toggle_fullscreen() # 退出全屏

    # 屏幕點擊切換
    def _on_screen_clicked(self, idx): # 點擊螢幕
        self.active_player_index = idx # 當前螢幕
        self.video_widget = self.video_widgets[self.active_player_index] # 焦點元件
        self.screen_mgr.update_screen_borders() # 更新外框
        self.screen_mgr._sync_audio_focus() # 音訊對焦
        self._update_bottom_control_bar_ui() # 更新底條
        self.sync_controls_ui() # 同步介面

    # -------------------- 輔助工具 --------------------
    # 保存歷史
    def save_history(self): # 保存歷史
        self._settings["history_sources"] = self.history_sources # 寫入歷史
        self._settings["history_list"] = self.history_sources # 寫入清單
        _save_settings(self._settings) # 儲存檔案

    # 收藏點擊
    def on_star_clicked(self, ch_data, star_btn): # 點擊最愛
        url = ch_data.get('url') # 取出網址
        if not url: # 網址為空
            return # 跳出方法
        fav_urls = {f['url'] for f in self.favorites_list if isinstance(f, dict) and 'url' in f} # 收集網址
        is_fav = url in fav_urls # 是否最愛
        if is_fav: # 已經最愛
            self.favorites_list = [f for f in self.favorites_list if isinstance(f, dict) and f.get('url') != url] # 移除最愛
            new_state = False # 新的狀態
        else: # 未加最愛
            self.favorites_list.append({'name': ch_data.get('name', '未知頻道'), 'url': url}) # 加入最愛
            new_state = True # 新的狀態
        star_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                outline: none;
                padding: 0px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
                border-radius: 15px;
            }
        """) # 按鈕樣式
        self._set_btn_svg_icon(star_btn, "star_filled" if new_state else "star_outline") # 切換圖示
        self._settings["favorites_list"] = self.favorites_list # 保存設定
        _save_settings(self._settings) # 寫入檔案

    # 頻道滾動加載
    def on_channel_scroll(self, value): # 滾動加載
        if self.channel_list: # 列表存在
            scrollbar = self.channel_list.verticalScrollBar() # 垂直滑軌
            if scrollbar.maximum() > 0 and value >= scrollbar.maximum() * 0.70: # 滾動過半
                self.channel_mgr.load_live_channels(reset=False) # 分頁加載

    # 質量過濾
    def set_quality_filter(self, filter_text, active_btn): # 畫質過濾
        self.current_quality = filter_text # 設定畫質
        accent = self.current_theme_accent # 主題色彩
        for btn in self.filter_btn_list: # 遍歷按鈕
            if btn == active_btn: # 當前按鈕
                btn.setStyleSheet(f"background-color: {accent}; color: white; border-radius: 12px; padding: 5px; font-size: 12px;") # 啟用樣式
            else: # 其他按鈕
                btn.setStyleSheet("background-color: transparent; color: #888; border: 1px solid #2a2a35; border-radius: 12px; padding: 5px; font-size: 12px;") # 停用樣式
        self.channel_mgr.load_live_channels(reset=True) # 重新加載

    # 音量增加
    def _volume_up(self): # 音量加
        if self.vol_slider: # 滑軌存在
            new_val = min(100, self.vol_slider.value() + 5) # 計算數值
            self.vol_slider.setValue(new_val) # 設定數值
            self.set_volume(new_val) # 調整音量

    # 音量降低
    def _volume_down(self): # 音量減
        if self.vol_slider: # 滑軌存在
            new_val = max(0, self.vol_slider.value() - 5) # 計算數值
            self.vol_slider.setValue(new_val) # 設定數值
            self.set_volume(new_val) # 調整音量

    # 切換硬件加速
    def toggle_hw(self): # 切換硬解
        self.hw_enabled = not self.hw_enabled # 反轉狀態
        active_w = self.get_active_widget() # 獲取窗口
        active_w.hw_enabled = self.hw_enabled # 同步狀態
        self._update_hw_btn_style() # 更新樣式
        active_w._set_property_string("hwdec", "auto" if self.hw_enabled else "no") # 發送屬性
        self._settings["hwdec"] = self.hw_enabled # 保存設定
        _save_settings(self._settings) # 寫入檔案

    # 安裝事件過濾器（預留）
    def _event_filter_install_for_widgets(self): # 安裝過濾
        widgets = self.video_widgets or self.video_frames # 視訊集合
        for w in widgets: # 遍歷元件
            w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu) # 右鍵菜單
            try: # 嘗試斷開
                w.customContextMenuRequested.disconnect() # 斷開舊訊
            except Exception: # 忽略錯誤
                pass # 繼續執行
            w.customContextMenuRequested.connect(lambda pos, target=w: self.screen_mgr._show_context_menu_for_widget(pos, target)) # 綁定菜單

    # 關閉單個分屏
    def _close_single_widget(self, widget): # 關閉窗口
        try: # 嘗試停止
            if hasattr(widget, "clear_media"): # 新介面：完全清空
                widget.clear_media() # 停止並清網址/名稱
            else: # 舊介面
                widget.stop() # 停止播放
                widget.has_media = False # 標記無媒
                widget.update() # 刷新畫面
        except Exception as e: # 捕捉例外
            print(f"關閉窗口異常: {e}") # 印異常訊
        self.screen_mgr._sync_audio_focus() # 音訊對焦
        
    # 截圖
    def take_snapshot(self): # 執行截圖
        active_w = self.get_active_widget() # 獲取窗口
        try: # 嘗試截圖
            success = active_w.screenshot() # 呼叫截圖
            if success: # 截圖成功
                if self.tip_label is not None: # 標籤存在
                    self.tip_label.deleteLater() # 刪除標籤
                self.tip_label = QLabel("📷 截圖成功 (已存至 snapshots)", self) # 新建標籤
                self.tip_label.setStyleSheet("background-color: #1a1a24; color: white; font-size: 14px; padding: 6px 12px; border-radius: 4px; border: 1px solid #5a32fa;") # 套用樣式
                self.tip_label.adjustSize() # 自適尺寸
                global_pos = active_w.mapToGlobal(QPoint(20, 20)) # 全局座標
                self.tip_label.move(self.mapFromGlobal(global_pos)) # 設定位置
                self.tip_label.show() # 顯示標籤
                self.tip_label.raise_() # 置於最上
                QTimer.singleShot(1500, self.tip_label.hide) # 延遲隱藏
        except Exception as e: # 截圖失敗
            print(f"mpv 截圖失敗: {e}") # 印失敗訊

    # 格式化時間
    @staticmethod
    def format_time(ms): # 時間格式
        if ms < 0: # 負數時間
            return "00:00" # 返回零值
        seconds = int(ms / 1000) # 計算秒數
        m, s = divmod(seconds, 60) # 分秒換算
        h, m = divmod(m, 60) # 時分換算
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}" # 返回字串