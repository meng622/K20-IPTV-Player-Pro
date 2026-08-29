# main_window.py
import os
import sys
import json
import time
from config import *
from datetime import datetime

# 外部模組引用
from pip_manager import PiPManager
from dialogs import SettingsDialog
from epg_panel import EPGPanelWidget
from drop_manager import DropManager
from control_bar import PlayerControlBar
from player_engine import MpvEmbedWidget
from screen_manager import ScreenManager
from skin import IconManager, SkinManager
from hotkey_and_help import HotkeyAndHelpManager
from config import _load_settings, _save_settings
from m3u_manager import M3U管理主視窗, M3UFetchWorker
from channel_panel import ChannelPanelManager, _clean_epg_key
from widgets import FlatGradientSlider, CustomSplitter, RoundedMenu
from epg_manager import EPGDatabase, EPGDownloaderWorker, MemoryEPGWorker


# ==================== K20 主播放器 ====================
class K20PlayerUI主視窗(QMainWindow):
    # -------------------- 初始化 --------------------
    def __init__(self):
        super().__init__()
        self.setWindowTitle("K20 IPTV Player Pro (Editor Version) v1.0.0")
        self.resize(1270, 660)

        # 1. 預先宣告所有UI組件與狀態屬性（徹底消滅 hasattr 的根源）
        self.is_seeking = False
        self.is_fullscreen_state = False
        self.last_layout_count = 1
        self.current_layout_count = 1
        self.current_url = ""
        self.current_channel_name = ""
        self.active_player_index = 0
        self.rendered_channel_count = 0
        self.current_quality = "全部"
        self.current_theme_accent = ""
        self._splitter_initialized = False
        
        self.sidebar_btns = []
        self.filter_btn_list = []
        self.all_channels_data = []
        self.filtered_channels_cache = []
        self.history_sources = []
        self.video_frames = []
        self.video_widgets = []
        self.epg_cache = {}
        self.current_group_filter = "全部分組"
        self.channel_latencies = {}
        self.channel_list_mode = "live"
        self.current_logo_template = ""
        self.local_media_list = []
        self.current_sort_mode = "default"
        self.channels = []
        self.epg_data = {}
        self.is_m3u_loading = False
        self.is_pip_mode = False
        self.current_theme_config = {}
        self.config = {}  # 或從檔案載入

        # UI 控制項屬性統一（全部初始化為 None，後續會由對應方法賦值）
        self.btn_play_pause = None
        self.play_btn = None
        self.volume_slider = None
        self.vol_slider = None
        self.seek_slider = None
        self.btn_mute = None
        self.btn_hw = None
        self.btn_aspect = None
        self.btn_audio = None
        self.btn_osd = None
        self.btn_sub = None
        self.btn_skin = None
        self.btn_screen_layout = None
        self.btn_epg_toggle = None
        self.video_widget = None
        self.lbl_current_time = None
        self.lbl_total_time = None

        # 其他可能被查問的屬性
        self.loading_bar = None
        self.epg_tip_label = None
        self.tip_label = None
        self.m3u_worker = None
        self._drag_pos = None
        self.btn_restore_pip = None
        self.sizegrip_pip = None
        self.channel_panel = None
        self.epg_panel = None
        self.channel_list = None
        self.sidebar = None
        self.bottom_bar = None
        self.player_layout = None
        self.current_m3u_url = ""

        # 2. 讀取設定檔與初始化 Timer
        self._settings = _load_settings()
        sources = self._settings.get("m3u_sources", [])
        self.m3u_sources = sources if isinstance(sources, list) else []
        self.favorites_list = self._settings.get("favorites_list", [])
        history_data = self._settings.get("history_list", []) or self._settings.get("history_sources", [])
        self.history_sources = history_data if isinstance(history_data, list) else []
        self.auto_play_last = self._settings.get("auto_play_last", False)
        self.hw_enabled = self._settings.get("hwdec", True)
        self.cache_mb = self._settings.get("cache_mb", 100)

        saved_url = self._settings.get("current_m3u_url")
        if saved_url:
            self.current_m3u_url = saved_url
        elif self.m3u_sources:
            active_item = next((s for s in self.m3u_sources if isinstance(s, dict) and s.get('active')), self.m3u_sources[0])
            self.current_m3u_url = active_item.get('url', '') if isinstance(active_item, dict) else ''

        # 定時器初始化
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(3000)
        self.hide_timer.timeout.connect(self.hide_fullscreen_bars)

        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(300)
        self.ui_timer.timeout.connect(self.update_ui_timer)
        self.ui_timer.start()

        self.seek_debounce_timer = QTimer(self)
        self.seek_debounce_timer.setSingleShot(True)
        self.pending_seek_target = None
        self.seek_debounce_timer.timeout.connect(self._do_real_seek)

        # 3. 先建立所有 Manager 實例
        self.skin_mgr = SkinManager(self)
        self.channel_mgr = ChannelPanelManager(self)
        self.screen_mgr = ScreenManager(self)
        self.hotkey_help_mgr = HotkeyAndHelpManager(self)
        self.pip_mgr = PiPManager(self)
        self.drop_mgr = DropManager(self)

        # 4. 建立 Layout 結構與 UI 組件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 必須先初始化 Hotkey 管理器（供 sidebar 按鈕綁定使用）
        self.shortcut_mgr = self.hotkey_help_mgr

        # 之後才初始化 sidebar
        self.channel_mgr.init_sidebar()

        # 建立中央無級拉伸 Splitter 與頻道面板
        orientation = getattr(Qt.Orientation, 'Horizontal', getattr(Qt, 'Horizontal', None))
        self.main_splitter = CustomSplitter(orientation, self)
        self.main_splitter.setObjectName("main_splitter")
        self.main_splitter.setOpaqueResize(True)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(3)

        # 將 Splitter 拖動信號直接綁定到控制欄調整函數
        self.main_splitter.splitterMoved.connect(lambda pos, index: self._auto_adjust_bottom_controls())

        # 直接抓取 Handle 實體物件，強制寫入樣式 (避開 Qt 原生繪製覆蓋)
        handle = self.main_splitter.handle(1)
        if handle:
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
            """)

        self.channel_mgr.init_channel_panel()
        # 現在 channel_panel 已由 channel_mgr 建立，賦值給 self.channel_panel
        
        if self.channel_panel:
            self.channel_panel.setMinimumWidth(300)
            self.channel_panel.setMaximumWidth(16777215)
            self.channel_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 建立播放區域
        self.init_player_area()

        # 建立右側 EPG 面板
        self.init_epg_panel()

        # 設定 Stretch Factor 權重
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        if self.epg_panel:
            self.main_splitter.setStretchFactor(2, 0)

        self.main_layout.addWidget(self.main_splitter, 0)

        # 5. 套用主題、加載數據與快捷鍵
        saved_theme = self._settings.get("theme", "purple")
        self.current_theme = saved_theme
        self.skin_mgr.apply_skin(saved_theme)

        self.load_initial_channels()

        if self.auto_play_last:
            last_url = self._settings.get("last_channel_url")
            if last_url:
                self.current_url = last_url
                self.current_channel_name = self._settings.get("last_channel_name", "上次觀看")
                self.update_header_title(channel_name=self.current_channel_name)
                QTimer.singleShot(800, lambda: self.video_widget.play(last_url))

        # 滑鼠移動監聽
        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)

        # 啟動時初始化 EPG 資料庫
        self.epg_db = EPGDatabase()

        # 開機時進行一次 UI 狀態校正
        self._update_bottom_control_bar_ui()

        # 玻璃 iOS skin2
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    # -------------------- UI構建 --------------------
    # 創建播放區
    def init_player_area(self):
        player_panel = QWidget()
        player_panel.setObjectName("player_panel")
        player_panel.setMinimumWidth(200)
        player_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        player_panel.setStyleSheet("QWidget#player_panel { background-color: #000000; }")

        layout = QVBoxLayout(player_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 頂欄
        self.top_bar = QWidget()
        self.top_bar.setObjectName("top_bar")
        self.top_bar.setFixedHeight(50)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(15, 0, 15, 0)

        menu_btn = QPushButton("")
        menu_btn.setObjectName("btn_menu_toggle")
        menu_btn.setFixedSize(46, 42)
        menu_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        menu_btn.setToolTip("開關頻道列表")
        menu_btn.clicked.connect(self.toggle_channel_panel)
        self._set_btn_svg_icon(menu_btn, "menu", QSize(36, 36))

        self.channel_info = QLabel("[直播流] - 請點擊左側頻道播放")
        self.channel_info.setStyleSheet("color: #ccc; font-size: 20px; background: transparent;")

        self.btn_epg_toggle = QPushButton("節目表")
        self.btn_epg_toggle.setObjectName("btn_epg_toggle")
        self.btn_epg_toggle.setCheckable(True)
        self.btn_epg_toggle.setProperty("role", "menu_btn")
        self.btn_epg_toggle.clicked.connect(self.toggle_epg_panel)
        self._set_btn_svg_icon(self.btn_epg_toggle, "epg")

        top_layout.addWidget(menu_btn)
        top_layout.addSpacing(10)
        top_layout.addWidget(self.channel_info)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_epg_toggle)

        # 四屏畫面區域
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: #000000;")
        self.grid_layout = QGridLayout(self.video_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(2)

        for i in range(4):
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.NoFrame)
            frame.setStyleSheet("background-color: #000000;")

            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(0, 0, 0, 0)
            frame_layout.setSpacing(0)

            # 取得緩存設定（預設 100 MB）
            cache_mb = self.config.get("cache_mb", 100)
            w = MpvEmbedWidget(cache_mb=cache_mb)
            w.hw_enabled = self.hw_enabled
            w.requestFullscreenToggle.connect(self.toggle_fullscreen)
            w.requestShowControls.connect(self._show_controls)

            frame_layout.addWidget(w)

            frame.installEventFilter(self)
            w.installEventFilter(self)

            self.video_frames.append(frame)
            self.video_widgets.append(w)
            w.has_media = False

        self.video_widget = self.video_widgets[0]

        # 統一主底欄控制條
        self.bottom_bar = PlayerControlBar(self)

        self.player_layout = layout
        self.player_layout.addWidget(self.top_bar)
        self.player_layout.addWidget(self.video_container, stretch=1)
        self.player_layout.addWidget(self.bottom_bar)

        self.main_splitter.addWidget(player_panel)
        player_panel.setMinimumWidth(500)
        self.screen_mgr.set_screen_layout(1)

    # 創建EPG面板
    def init_epg_panel(self):
        self.epg_panel = EPGPanelWidget(self)
        self.main_splitter.addWidget(self.epg_panel)
        self.epg_panel.setVisible(False)

    # 設置SVG圖標
    def _set_btn_svg_icon(self, btn, icon_name, icon_size=None):
        if icon_size is not None:
            btn.setIconSize(icon_size)
        cur_size = btn.iconSize()
        if cur_size.width() == 0 or cur_size.height() == 0:
            cur_size = QSize(18, 18)
            btn.setIconSize(cur_size)
        icon = IconManager.get_icon(icon_name, size=cur_size.width())
        btn.setIcon(icon)

    # 自適應底部欄
    def _auto_adjust_bottom_controls(self):
        if self.bottom_bar:
            self.bottom_bar.auto_adjust_controls()

    # 調整分割比例
    def adjust_splitter_ratios(self):
        total_w = self.main_splitter.width()
        if total_w <= 0:
            return
        if not self._splitter_initialized:
            self._splitter_initialized = True
            left_w = 240 if self.channel_panel and self.channel_panel.isVisible() else 0
            right_w = 220 if self.epg_panel and self.epg_panel.isVisible() else 0
            if total_w <= 1280:
                left_w = 200 if left_w > 0 else 0
                right_w = 180 if right_w > 0 else 0
            center_w = total_w - left_w - right_w
            sizes = [left_w, center_w]
            if self.epg_panel and self.epg_panel.isVisible():
                sizes.append(right_w)
            self.main_splitter.setSizes(sizes)

    # -------------------- 頻道與EPG加載 --------------------
    # 載入初始頻道
    def load_initial_channels(self):
        target_url = self._settings.get("current_m3u_url") if isinstance(self._settings, dict) else None
        if not target_url and self.current_m3u_url:
            target_url = self.current_m3u_url
        if not target_url and self.m3u_sources:
            target_url = self.m3u_sources[0]['url']

        if target_url:
            self.start_parse_m3u(target_url)

        epg_url = self._settings.get("epg_url", "") or self._settings.get("current_epg_url", "")
        if self.channel_mgr:
            print(f"🔍 [DEBUG] 正在準備啟動 EPG，從設定檔讀取到的網址為: '{epg_url}'")
            self.channel_mgr.load_epg_data(epg_url)

    # 解析M3U文件
    def start_parse_m3u(self, m3u_path_or_url):
        self.is_m3u_loading = True
        self.all_channels = []

        self.channel_mgr.load_live_channels(reset=True)
        
        if self.loading_bar is not None:
            self.loading_bar.setRange(0, 100)
            self.loading_bar.setValue(0)
            self.loading_bar.setVisible(True)

        if self.channel_mgr:
            self.channel_mgr.load_live_channels(reset=True)

        if self.m3u_worker and self.m3u_worker.isRunning():
            self.m3u_worker.quit()
            self.m3u_worker.wait(1000)

        self.m3u_worker = M3UFetchWorker(m3u_path_or_url)
        self.m3u_worker.finished_signal.connect(self.on_m3u_parsed)
        # progress_signal 必定存在，直接連接
        self.m3u_worker.progress_signal.connect(self.on_m3u_progress)

        self.m3u_worker.start()

        # 清空舊資料並立即觸發 UI 渲染
        self.all_channels = []
        self.channel_mgr.load_live_channels(reset=True)

    # M3U解析進度
    def on_m3u_progress(self, current, total):
        if self.loading_bar is not None and total > 0:
            self.loading_bar.setMaximum(total)
            self.loading_bar.setValue(current)

    # M3U解析完成
    def on_m3u_parsed(self, *args, **kwargs):
        print("✅ [DEBUG] on_m3u_parsed 被触发了！")
        channels = args[0] if args else kwargs.get('channels', [])
        epg_url = args[1] if len(args) > 1 else kwargs.get('epg_url', '')

        self.is_m3u_loading = False
        if self.loading_bar is not None:
            self.loading_bar.setVisible(False)

        self.all_channels_data = channels
        print(f"📦 [DEBUG] M3U 解析完成，收到 {len(channels) if isinstance(channels, list) else 0} 個頻道，EPG 網址: '{epg_url}'")

        if self.channel_mgr:
            mgr = self.channel_mgr
            mgr.channels = channels
            mgr.all_channels = channels
            if mgr:
                mgr.load_live_channels(reset=True)
                print("✅ [DEBUG] 已執行 mgr.load_live_channels(reset=True)")

        setting_epg = ""
        if isinstance(self._settings, dict):
            setting_epg = self._settings.get("epg_url", "") or self._settings.get("current_epg_url", "")

        target_epg_url = setting_epg or epg_url

        if target_epg_url and self.channel_mgr:
            self.channel_mgr.load_epg_data(target_epg_url)

        # 直接切換到「電視直播」頁面
        first_btn = self.sidebar_btns[0] if self.sidebar_btns else None
        self.channel_mgr.switch_channel_view("live", first_btn)

    # 載入EPG數據
    def load_epg(self, epg_url):
        self.setEnabled(False)

        if self.loading_bar is not None:
            self.loading_bar.setVisible(True)
            self.loading_bar.setFixedHeight(50)
            self.loading_bar.setFixedWidth(245)
            self.loading_bar.setValue(0)
            self.loading_bar.setFormat(" %p% [%v/%m]")

            if self.epg_tip_label is None:
                self.epg_tip_label = QLabel(self)
                self.epg_tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # 套用主題顏色
            self.update_dynamic_theme()
            self.epg_tip_label.setText("⏳ 正在加載 EPG 節目標題...\n請耐心等候，\n請勿點擊造成卡頓！\n如果10秒之內都無法加載，\n請完全退出播放器，從新打開。\n如果依然不行，請打任務管理器\n“結束進程”或重啟電腦")
            bar_geo = self.loading_bar.geometry()
            self.epg_tip_label.setGeometry(bar_geo.x() + 50, bar_geo.y() + 65, 270, 380)
            self.epg_tip_label.setVisible(True)
            self.epg_tip_label.raise_()

        QApplication.processEvents()

        self.epg_memory_worker = MemoryEPGWorker(epg_url)
        self.epg_memory_worker.finished_signal.connect(self.on_epg_memory_loaded)
        self.epg_memory_worker.start()

    # 動態主題更新
    def update_dynamic_theme(self):
        if self.epg_tip_label is not None:
            accent = self.current_theme_accent
            self.epg_tip_label.setStyleSheet(f"""
                color: {accent};
                font-size: 16px;
                font-weight: bold;
                background: rgba(30, 30, 36, 0.9);
                border: 1px solid {accent};
                border-radius: 10px;
                padding: 4px;
            """)

    # EPG記憶載入
    def on_epg_memory_loaded(self, data):
        self.epg_data = data
        total_count = len(data) if data else 100

        if self.loading_bar is not None:
            self.loading_bar.setRange(0, total_count)

        if self.epg_panel:
            self.epg_panel.update_epg_content()

        if self.loading_bar is not None:
            step_chunk = total_count / 10.0
            for step in range(1, 6):
                self.loading_bar.setValue(int(step_chunk * step))
                QApplication.processEvents()
                QThread.msleep(20)

        if self.channel_mgr:
            self.channel_mgr.load_live_channels(reset=True)

        if self.loading_bar is not None:
            for step in range(6, 11):
                self.loading_bar.setValue(int(step_chunk * step))
                QApplication.processEvents()
                QThread.msleep(20)

        def unlock_ui():
            if self.loading_bar is not None:
                self.loading_bar.setVisible(False)
            if self.epg_tip_label is not None:
                self.epg_tip_label.setVisible(False)
            self.setEnabled(True)
            print(f"✅ 內存 EPG 加載完成，共索引 {len(data)} 個頻道")

        QTimer.singleShot(200, unlock_ui)

    # EPG下載完成
    def on_epg_download_finished(self, success, msg):
        print(f"EPG 載入狀態: {msg}")
        if success and self.epg_panel:
            QTimer.singleShot(500, lambda: self.epg_panel.update_epg_content())

    # 更新EPG內容
    def update_epg_content(self, channel_name=None):
        if self.epg_panel:
            self.epg_panel.update_epg_content(channel_name)

    # -------------------- 播放控制 --------------------
    # 播放指定頻道
    def play_channel(self, item, custom_epg="", channel_name=""):
        url = None
        ch_name = channel_name
        ch_obj = {}

        if hasattr(item, 'data'): # 保留 hasattr，因為 item 可能係 dict
            data = item.data(Qt.ItemDataRole.UserRole)
            ch_obj = item.data(Qt.ItemDataRole.UserRole + 1) or {}
            if isinstance(data, dict):
                url = data.get('url')
                ch_name = data.get('name') or data.get('tvg_name') or data.get('tvg-name') or ""
                ch_obj = data
            elif isinstance(data, str):
                url = data
        elif isinstance(item, dict):
            url = item.get('url')
            ch_name = item.get('name') or item.get('tvg_name') or item.get('tvg-name') or ""
            ch_obj = item

        # 1. 備用路徑 A：從 item.text() 嘗試讀取
        if not ch_name and hasattr(item, 'text') and callable(item.text):
            ch_name = item.text().strip()

        # 2. 備用路徑 B：直擊核心！如果還是拿不到，直接從左側卡片 Widget 的 QLabel 提取頻道名
        if not ch_name and item and hasattr(self, 'channel_mgr'):
            try:
                w = self.channel_mgr.channel_list.itemWidget(item)
                if w:
                    for lbl in w.findChildren(QLabel):
                        txt = lbl.text().strip()
                        # 過濾掉 EPG 行（帶 ▶ 的）和數字，剩下的就是頻道名稱
                        if txt and '▶' not in txt and not txt.isdigit():
                            ch_name = txt
                            break
            except Exception:
                pass

        if not ch_name:
            ch_name = "直播頻道"

        if not url:
            return

        epg_text = ""
        if isinstance(ch_obj, dict):
            epg_text = ch_obj.get('epg') or ch_obj.get('current_program') or ch_obj.get('epg_title') or ""

        self.current_url = url
        self.current_channel_name = ch_name
        self.current_channel_obj = ch_obj if isinstance(ch_obj, dict) else {'name': ch_name, 'url': url}

        self.update_header_title(channel_name=ch_name, custom_epg=custom_epg)

        target_widget = self.get_active_widget()

        target_widget.has_media = True
        target_widget.play(url)

        self._set_btn_svg_icon(self.play_btn, "pause")
        QTimer.singleShot(800, lambda: self._set_btn_svg_icon(self.play_btn, "pause"))

        self.screen_mgr._sync_audio_focus()
        QTimer.singleShot(300, self.screen_mgr._sync_audio_focus)

        history_item = {'name': ch_name, 'url': url, 'time': int(time.time())}
        self.history_sources = [h for h in self.history_sources if isinstance(h, dict) and h.get('url') != url]
        self.history_sources.insert(0, history_item)
        self.history_sources = self.history_sources[:100]

        self._settings["history_list"] = self.history_sources
        self._settings["history_sources"] = self.history_sources
        self._settings["last_channel_url"] = url
        self._settings["last_channel_name"] = ch_name
        _save_settings(self._settings)

        self._set_btn_svg_icon(self.play_btn, "pause")
        if self.epg_panel and self.epg_panel.isVisible():
            self.update_epg_content()

    # 切換播放暫停
    def toggle_play(self):
        active_w = self.get_active_widget()
        if active_w.is_paused:
            active_w.resume()
        else:
            active_w.pause()
            self._update_bottom_control_bar_ui()

    # MPV暫停變更
    def _on_mpv_pause_changed(self, is_paused):
        icon_name = "play" if is_paused else "pause"
        if self.play_btn is not None:
            self._set_btn_svg_icon(self.play_btn, icon_name)

    # 停止播放
    def stop_play(self):
        active_w = self.get_active_widget()
        if active_w:
            active_w._set_property_string("time-pos", "0")
            active_w.pause()
            self._set_btn_svg_icon(self.play_btn, "play")
            if self.lbl_current_time:
                self.lbl_current_time.setText("00:00")
            if self.seek_slider:
                self.seek_slider.setValue(0)

    # 相對尋道
    def seek_offset(self, offset_sec):
        target_player = self.get_active_widget()
        if target_player and target_player.mpv:
            target_player.mpv.command("seek", offset_sec, "relative+exact")

    # 按下進度條
    def on_seek_pressed(self):
        self.is_seeking = True

    # 釋放進度條
    def on_seek_released(self):
        val = self.seek_slider.value() if self.seek_slider else 0
        target_player = self.get_active_widget()

        duration = target_player.get_duration()

        if duration > 0:
            target_pos = (val / 1000.0) * duration
            self.pending_seek_target = target_pos
            self.seek_debounce_timer.start(300)

        self.is_seeking = False

    def _do_real_seek(self):
        if self.pending_seek_target is not None:
            target_player = self.get_active_widget()
            if target_player and target_player.mpv:
                target_player.mpv.command('seek', self.pending_seek_target, 'absolute')
            self.pending_seek_target = None

    # 設置音量
    def set_volume(self, value):
        active_w = self.get_active_widget()
        if not active_w:
            return
        active_w.set_volume(value)
        is_muted = active_w.get_mute()
        if self.btn_mute:
            self._set_btn_svg_icon(self.btn_mute, "mute" if (value == 0 or is_muted) else "volume")

    # 切換靜音
    def toggle_mute(self):
        active_w = self.get_active_widget()
        if not active_w:
            return
        current_mute = active_w.get_mute()
        active_w.set_mute(not current_mute)
        self.sync_controls_ui()

    # 獲取當前活動窗口
    def get_active_widget(self):
        if self.video_widgets and 0 <= self.active_player_index < len(self.video_widgets):
            return self.video_widgets[self.active_player_index]
        return self.video_widget

    # 更新底部控制欄UI
    def _update_bottom_control_bar_ui(self):
        active_w = self.get_active_widget()
        if not active_w:
            return
        try:
            is_paused = active_w.is_paused
            icon_name = "play" if is_paused else "pause"
            if self.play_btn:
                self.play_btn.setText("")
                self._set_btn_svg_icon(self.play_btn, icon_name)
            cur_vol = active_w.get_volume()
            if self.vol_slider:
                self.vol_slider.blockSignals(True)
                self.vol_slider.setValue(int(cur_vol if cur_vol is not None else 100))
                self.vol_slider.blockSignals(False)
        except Exception:
            pass

    # 更新頂部標題
    def update_header_title(self, channel_name=None, custom_title=None, custom_epg=None):
        if channel_name:
            self.current_channel_name = channel_name
            epg_clean = custom_epg.strip() if custom_epg else ""
            if epg_clean:
                if not epg_clean.startswith('▶'):
                    epg_clean = f"▶{epg_clean}"
                display_str = f"[直播流] - {channel_name} - {epg_clean}"
            else:
                display_str = f"[直播流] - {channel_name} - 無節目資訊"
        elif custom_title:
            display_str = str(custom_title)
        else:
            display_str = "[無播放資訊]"
        self.channel_info.setText(display_str)
        self.setWindowTitle(f"K20 IPTV Player Pro (Editor Version) v1.0.0 - {display_str}")

    # 同步控制UI
    def sync_controls_ui(self):
        self._update_bottom_control_bar_ui()
        active_w = self.get_active_widget()
        if not active_w:
            return
        is_muted = active_w.get_mute()
        vol = active_w.get_volume()
        if self.vol_slider:
            self.vol_slider.blockSignals(True)
            self.vol_slider.setValue(int(vol))
            self.vol_slider.blockSignals(False)
        if self.btn_mute:
            self._set_btn_svg_icon(self.btn_mute, "mute" if (is_muted or vol == 0) else "volume")

    # 定時更新UI
    def update_ui_timer(self):
        active_w = self.get_active_widget()
        if not active_w or not active_w.mpv:
            return
        try:
            duration = active_w.get_duration()
            pos = active_w.get_time_pos()
            if duration and duration > 0:
                if not self.is_seeking and self.seek_slider:
                    self.seek_slider.setValue(int((pos / duration) * 1000))
                if self.lbl_current_time:
                    self.lbl_current_time.setText(self.format_time(int(pos * 1000)))
                if self.lbl_total_time:
                    self.lbl_total_time.setText(self.format_time(int(duration * 1000)))
                if self.seek_slider:
                    self.seek_slider.setEnabled(True)
            else:
                if self.lbl_current_time:
                    self.lbl_current_time.setText("00:00")
                if self.lbl_total_time:
                    self.lbl_total_time.setText("00:00")
                if self.seek_slider:
                    self.seek_slider.setValue(0)
                    self.seek_slider.setEnabled(False)
            self._update_bottom_control_bar_ui()
        except Exception:
            pass

    # 顯示OSD
    def show_osd(self):
        if self.video_widgets:
            self.video_widgets[0].mpv.toggle_stats()

    # -------------------- 全屏與面板切換 --------------------
    # 切換全屏
    def toggle_fullscreen(self):
        if self.pip_mgr and self.pip_mgr.is_pip_mode:
            return
        if self.isFullScreen():
            if self.bottom_bar:
                self.bottom_bar.clearMask()
                self.bottom_bar.setWindowFlags(Qt.WindowType.Widget)
                self.bottom_bar.setMinimumSize(0, 0)
                self.bottom_bar.setMaximumSize(16777215, 16777215)
                self.bottom_bar.setFixedHeight(100)
                self.bottom_bar.setStyleSheet("")
                self.bottom_bar.setObjectName("bottom_bar")
            self.showNormal()
            if self.sidebar is not None:
                self.sidebar.setVisible(True)
            if self.channel_panel is not None:
                self.channel_panel.setVisible(True)
            if self.top_bar:
                self.top_bar.setVisible(True)
            if self.bottom_bar:
                self.bottom_bar.setVisible(True)
            if self.player_layout is not None and self.bottom_bar:
                self.bottom_bar.setParent(None)
                self.player_layout.addWidget(self.bottom_bar)
            self.hide_timer.stop()
            self.unsetCursor()
            self.adjust_splitter_ratios()
        else:
            if self.sidebar is not None:
                self.sidebar.setVisible(False)
            if self.channel_panel is not None:
                self.channel_panel.setVisible(False)
            if self.top_bar:
                self.top_bar.setVisible(False)
            if self.bottom_bar:
                self.bottom_bar.setParent(None)
                self.bottom_bar.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
                self.bottom_bar.hide()
            self.showFullScreen()
            self.hide_timer.start()
        current = getattr(self, 'current_theme', 'purple')
        self.skin_mgr.apply_skin(current)

    # 顯示全屏控制欄
    def _show_controls(self):
        if self.isFullScreen():
            if self.bottom_bar and self.bottom_bar.isVisible() and self.bottom_bar.windowOpacity() >= 0.99:
                self.hide_timer.start()
                return
            MARGIN_X = 40
            screen_geom = self.screen().geometry()
            vw = screen_geom.width() - (MARGIN_X * 2)
            bh = 100
            OFFSET_Y = 30
            target_x = screen_geom.x() + MARGIN_X
            target_y = screen_geom.y() + screen_geom.height() - bh - OFFSET_Y
            if self.bottom_bar:
                self.bottom_bar.setFixedSize(vw, bh)
                self.bottom_bar.setGeometry(target_x, target_y, vw, bh)
                path = QPainterPath()
                path.addRoundedRect(QRectF(0, 0, vw, bh), 12, 12)
                self.bottom_bar.setMask(QRegion(path.toFillPolygon().toPolygon()))
                self.bottom_bar.fade_in()
                self.bottom_bar.raise_()
            self.unsetCursor()
            self.hide_timer.start()

    # 隱藏全屏控制欄
    def hide_fullscreen_bars(self):
        if self.isFullScreen():
            if self.bottom_bar and getattr(self.bottom_bar, '_is_fading', False):
                self.hide_timer.start()
                return
            if self.bottom_bar:
                self.bottom_bar.fade_out()
            if self.top_bar:
                self.top_bar.hide()
            self.setCursor(Qt.CursorShape.BlankCursor)

    # 切換頻道面板
    def toggle_channel_panel(self):
        if self.channel_panel is None:
            return
        is_visible = self.channel_panel.isVisible()
        self.channel_panel.setVisible(not is_visible)
        self.adjust_splitter_ratios()
        QTimer.singleShot(20, self._auto_adjust_bottom_controls)

    # 切換EPG面板
    def toggle_epg_panel(self):
        if self.epg_panel:
            self.epg_panel.toggle_panel()

    # 切換畫中畫
    def toggle_pip(self):
        self.pip_mgr.toggle()

    # -------------------- 菜單與樣式 --------------------
    # 皮膚菜單
    def show_skin_menu(self):
        menu = RoundedMenu(self)
        menu.addAction("🟣 暗黑魅紫 (Default)", lambda: self.skin_mgr.apply_skin("purple"))
        menu.addAction("🔷 賽博霓藍", lambda: self.skin_mgr.apply_skin("cyan"))
        menu.addAction("🟢 翡翠極光", lambda: self.skin_mgr.apply_skin("emerald"))
        menu.addAction("🩶 鈦空深灰", lambda: self.skin_mgr.apply_skin("slate"))
        if self.btn_skin:
            menu.exec(self.btn_skin.mapToGlobal(QPoint(0, self.btn_skin.height())))

    # 佈局菜單
    def show_screen_layout_menu(self):
        menu = RoundedMenu(self)
        menu.addAction("單屏模式 (標準)", lambda: self.screen_mgr.set_screen_layout(1))
        menu.addAction("雙屏模式 (左右)", lambda: self.screen_mgr.set_screen_layout(2))
        menu.addAction("三屏模式 (1:2)", lambda: self.screen_mgr.set_screen_layout(3))
        menu.addAction("四屏模式 (田字)", lambda: self.screen_mgr.set_screen_layout(4))
        if self.btn_screen_layout:
            menu.exec(self.btn_screen_layout.mapToGlobal(QPoint(0, self.btn_screen_layout.height())))

    # 寬高比菜單
    def show_aspect_menu(self):
        menu = RoundedMenu(self)
        active_w = self.get_active_widget()
        ratios = [
            ("預設 (原始)", None),
            ("16:10", 16 / 10),
            ("18:9", 18 / 9),
            ("21:9", 21 / 9),
            ("16:9", 16 / 9),
            ("4:3", 4 / 3),
            ("1:1", 1 / 1),
            ("填滿畫面", -1)
        ]
        for label, ratio in ratios:
            action = QAction(label, self)
            action.triggered.connect(lambda _, r=ratio, w=active_w: w.set_aspect(r))
            menu.addAction(action)
        if self.btn_aspect:
            menu.exec(self.btn_aspect.mapToGlobal(self.btn_aspect.rect().bottomLeft()))

    # 音軌菜單
    def show_audio_menu(self):
        menu = RoundedMenu(self)
        active_w = self.get_active_widget()
        track_json = active_w.get_property_string("track-list")
        current_aid = active_w.get_property_string("aid") or "no"
        if not track_json:
            menu.addAction(QAction("無可用音軌", self))
            if self.btn_audio:
                menu.exec(self.btn_audio.mapToGlobal(self.btn_audio.rect().bottomLeft()))
            return
        try:
            tracks = json.loads(track_json)
            audio_tracks = [t for t in tracks if t.get("type") == "audio"]
            if not audio_tracks:
                menu.addAction(QAction("無可用音軌", self))
            else:
                seen_langs = set()
                for t in audio_tracks:
                    tid = str(t.get("id", ""))
                    raw_title = t.get("title", "") or t.get("lang", "") or f"音軌 {tid}"
                    clean_title = raw_title
                    if "audio only" in raw_title:
                        if "(" in raw_title and ")" in raw_title:
                            clean_title = raw_title[raw_title.find("(")+1:raw_title.rfind(")")]
                    if clean_title in seen_langs:
                        continue
                    seen_langs.add(clean_title)
                    label = f"{'✅ ' if tid == current_aid else ''}{clean_title}"
                    action = QAction(label, self)
                    action.triggered.connect(lambda _, id=tid, w=active_w: w._set_property_string("aid", id))
                    menu.addAction(action)
        except Exception:
            menu.addAction(QAction("無可用音軌", self))
        if self.btn_audio:
            menu.exec(self.btn_audio.mapToGlobal(self.btn_audio.rect().bottomLeft()))

    # 字幕菜單
    def show_subtitle_menu(self):
        menu = RoundedMenu(self)
        active_w = self.get_active_widget()
        track_json = active_w.get_property_string("track-list")
        current_sid = active_w.get_property_string("sid") or "no"
        if not track_json:
            menu.addAction(QAction("無可用字幕", self))
            if self.btn_sub:
                menu.exec(self.btn_sub.mapToGlobal(self.btn_sub.rect().bottomLeft()))
            return
        try:
            tracks = json.loads(track_json)
            sub_tracks = [t for t in tracks if t.get("type") == "sub"]
            if not sub_tracks:
                menu.addAction(QAction("無可用字幕", self))
            else:
                for t in sub_tracks:
                    tid = str(t.get("id", ""))
                    ttitle = t.get("title", "") or t.get("lang", "") or f"字幕 {tid}"
                    label = f"{'✅ ' if tid == current_sid else ''}{ttitle}"
                    action = QAction(label, self)
                    action.triggered.connect(lambda _, id=tid, w=active_w: w._set_property_string("sid", id))
                    menu.addAction(action)
                menu.addSeparator()
                off = QAction("❌ 關閉字幕", self)
                off.triggered.connect(lambda checked=False, w=active_w: w._set_property_string("sid", "no"))
                menu.addAction(off)
        except Exception:
            menu.addAction(QAction("無可用字幕", self))
        if self.btn_sub:
            menu.exec(self.btn_sub.mapToGlobal(self.btn_sub.rect().bottomLeft()))

    # 更新側邊欄樣式
    def update_sidebar_btn_styles(self, active_btn):
        self.current_sidebar_btn = active_btn
        accent = self.current_theme_accent
        for btn in self.sidebar_btns:
            icon_name = btn.property("icon_name")
            is_active = (btn == active_btn)
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            if icon_name:
                color = accent if is_active else "#FFFFFF"
                icon = IconManager.get_icon(icon_name, color=color, size=22)
                btn.setIcon(icon)

    # 更新硬件加速按鈕
    def _update_hw_btn_style(self):
        accent = self.current_theme_accent
        if self.hw_enabled:
            self.btn_hw.setStyleSheet(f"""
                QPushButton {{
                    background-color: {accent} !important;
                    border: 1px solid {accent} !important;
                    border-radius: 12px !important;
                }}
            """)
            self.btn_hw.setToolTip("HW: On")
        else:
            self.btn_hw.setStyleSheet("")
            self.btn_hw.setToolTip("HW: Off")
        self.btn_hw.style().unpolish(self.btn_hw)
        self.btn_hw.style().polish(self.btn_hw)
        self.btn_hw.update()

    # -------------------- 事件處理 --------------------
    # 事件過濾器
    def eventFilter(self, watched, event):
        if watched == self.video_widget and self.is_pip_mode:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                pos = event.pos()
                btn_hit = (self.btn_restore_pip is not None and self.btn_restore_pip.isVisible() and self.btn_restore_pip.geometry().contains(pos))
                grip_hit = (self.sizegrip_pip is not None and self.sizegrip_pip.isVisible() and self.sizegrip_pip.geometry().contains(pos))
                if not btn_hit and not grip_hit:
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True
            elif event.type() == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
                if self._drag_pos is not None:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_pos = None
        return super().eventFilter(watched, event)

    # 鼠標移動事件
    def mouseMoveEvent(self, event):
        if self.isFullScreen():
            if self.bottom_bar and self.bottom_bar.isVisible() and self.bottom_bar.windowOpacity() >= 0.99:
                self.hide_timer.start()
            else:
                self._show_controls()
        super().mouseMoveEvent(event)

    # 窗口尺寸變化
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._auto_adjust_bottom_controls()

    # 窗口顯示事件
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._auto_adjust_bottom_controls)

    # ESC鍵處理
    def _esc_handler(self):
        if self.isFullScreen():
            self.toggle_fullscreen()

    # 屏幕點擊切換
    def _on_screen_clicked(self, idx):
        self.active_player_index = idx
        self.video_widget = self.video_widgets[self.active_player_index]
        self.screen_mgr.update_screen_borders()
        self.screen_mgr._sync_audio_focus()
        self._update_bottom_control_bar_ui()
        self.sync_controls_ui()

    # -------------------- 輔助工具 --------------------
    # 保存歷史
    def save_history(self):
        self._settings["history_sources"] = self.history_sources
        self._settings["history_list"] = self.history_sources
        _save_settings(self._settings)

    # 收藏點擊
    def on_star_clicked(self, ch_data, star_btn):
        url = ch_data.get('url')
        if not url:
            return
        fav_urls = {f['url'] for f in self.favorites_list if isinstance(f, dict) and 'url' in f}
        is_fav = url in fav_urls
        if is_fav:
            self.favorites_list = [f for f in self.favorites_list if isinstance(f, dict) and f.get('url') != url]
            new_state = False
        else:
            self.favorites_list.append({'name': ch_data.get('name', '未知頻道'), 'url': url})
            new_state = True
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
        """)
        self._set_btn_svg_icon(star_btn, "star_filled" if new_state else "star_outline")
        self._settings["favorites_list"] = self.favorites_list
        _save_settings(self._settings)

    # 頻道滾動加載
    def on_channel_scroll(self, value):
        if self.channel_list:
            scrollbar = self.channel_list.verticalScrollBar()
            if scrollbar.maximum() > 0 and value >= scrollbar.maximum() * 0.70:
                self.channel_mgr.load_live_channels(reset=False)

    # 質量過濾
    def set_quality_filter(self, filter_text, active_btn):
        self.current_quality = filter_text
        accent = self.current_theme_accent
        for btn in self.filter_btn_list:
            if btn == active_btn:
                btn.setStyleSheet(f"background-color: {accent}; color: white; border-radius: 12px; padding: 5px; font-size: 12px;")
            else:
                btn.setStyleSheet("background-color: transparent; color: #888; border: 1px solid #2a2a35; border-radius: 12px; padding: 5px; font-size: 12px;")
        self.channel_mgr.load_live_channels(reset=True)

    # 音量增加
    def _volume_up(self):
        if self.vol_slider:
            new_val = min(100, self.vol_slider.value() + 5)
            self.vol_slider.setValue(new_val)
            self.set_volume(new_val)

    # 音量降低
    def _volume_down(self):
        if self.vol_slider:
            new_val = max(0, self.vol_slider.value() - 5)
            self.vol_slider.setValue(new_val)
            self.set_volume(new_val)

    # 切換硬件加速
    def toggle_hw(self):
        self.hw_enabled = not self.hw_enabled
        active_w = self.get_active_widget()
        active_w.hw_enabled = self.hw_enabled
        self._update_hw_btn_style()
        active_w._set_property_string("hwdec", "auto" if self.hw_enabled else "no")
        self._settings["hwdec"] = self.hw_enabled
        _save_settings(self._settings)

    # 安裝事件過濾器（預留）
    def _event_filter_install_for_widgets(self):
        widgets = self.video_widgets or self.video_frames
        for w in widgets:
            w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            try:
                w.customContextMenuRequested.disconnect()
            except Exception:
                pass
            w.customContextMenuRequested.connect(lambda pos, target=w: self.screen_mgr._show_context_menu_for_widget(pos, target))

    # 關閉單個分屏
    def _close_single_widget(self, widget):
        try:
            widget.stop()
        except Exception as e:
            print(f"關閉窗口異常: {e}")
        widget.has_media = False
        widget.update()
        self.screen_mgr._sync_audio_focus()
        
    # 截圖
    def take_snapshot(self):
        active_w = self.get_active_widget()
        try:
            success = active_w.screenshot()
            if success:
                if self.tip_label is not None:
                    self.tip_label.deleteLater()
                self.tip_label = QLabel("📷 截圖成功 (已存至 snapshots)", self)
                self.tip_label.setStyleSheet("background-color: #1a1a24; color: white; font-size: 14px; padding: 6px 12px; border-radius: 4px; border: 1px solid #5a32fa;")
                self.tip_label.adjustSize()
                global_pos = active_w.mapToGlobal(QPoint(20, 20))
                self.tip_label.move(self.mapFromGlobal(global_pos))
                self.tip_label.show()
                self.tip_label.raise_()
                QTimer.singleShot(1500, self.tip_label.hide)
        except Exception as e:
            print(f"mpv 截圖失敗: {e}")

    # 格式化時間
    @staticmethod
    def format_time(ms):
        if ms < 0:
            return "00:00"
        seconds = int(ms / 1000)
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
