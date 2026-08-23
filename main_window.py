import os
import json
import time
from config import *
from datetime import datetime

# 外部模組引用
from skin import IconManager
from skin import SkinManager
from dialogs import SettingsDialog
from player_engine import MpvEmbedWidget
from screen_manager import ScreenManager
from config import _load_settings, _save_settings
from m3u_manager import M3U管理器主視窗, M3UFetchWorker
from epg_manager import EPGDatabase, EPGDownloaderWorker
from hotkey_and_help import HotkeyAndHelpManager
from channel_panel import ChannelPanelManager, _clean_epg_key
from widgets import FlatGradientSlider, CustomSplitter, RoundedMenu
from pip_manager import PiPManager
from epg_panel import EPGPanelWidget
from control_bar import PlayerControlBar
from drop_manager import DropManager

# ==================== K20 主播放器 ====================
class K20PlayerUI主視窗(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("K20 IPTV Player Pro (Editor Version) v1.0.0")
        self.resize(1270, 660)  # 🎯 每次打開預設 Resize 1280x720

        # --------------------------------------------------
        # 1. 預先宣告所有UI組件與狀態屬性
        # --------------------------------------------------
        self.is_seeking = False
        self.is_fullscreen_state = False
        self.last_layout_count = 1
        self.current_layout_count = 1
        self.current_url = ""
        self.current_channel_name = ""
        self.active_player_index = 0
        self.rendered_channel_count = 0
        self.current_quality = "全部"
        self.current_theme_accent = "#8b5cf6"

        self.sidebar_btns = []
        self.filter_btn_list = []
        self.all_channels_data = []
        self.filtered_channels_cache = []
        self.history_sources = []
        self.video_frames = []
        self.video_widgets = []
        self.epg_cache = {}

        # UI 控制項屬性統一
        self.btn_play_pause = None
        self.play_btn = None
        self.volume_slider = None
        self.vol_slider = None
        self.seek_slider = None
        self.btn_mute = None
        self.btn_hw = None
        self.btn_aspect = None
        self.btn_audio = None
        self.btn_sub = None
        self.btn_skin = None
        self.btn_screen_layout = None
        self.btn_epg_toggle = None
        self.video_widget = None

        # --------------------------------------------------
        # 2. 讀取設定檔與初始化 Timer
        # --------------------------------------------------
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
        else:
            self.current_m3u_url = ''

        # 定時器初始化
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(3000)
        self.hide_timer.timeout.connect(self.hide_fullscreen_bars)

        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(500)
        self.ui_timer.timeout.connect(self.update_ui_timer)
        self.ui_timer.start()

        self.seek_debounce_timer = QTimer(self)
        self.seek_debounce_timer.setSingleShot(True)
        self.pending_seek_target = None
        self.seek_debounce_timer.timeout.connect(self._do_real_seek)

        # --------------------------------------------------
        # 3. 先建立所有 Manager 實例
        # --------------------------------------------------
        self.skin_mgr = SkinManager(self)
        self.channel_mgr = ChannelPanelManager(self)
        self.screen_mgr = ScreenManager(self)
        self.hotkey_help_mgr = HotkeyAndHelpManager(self)
        self.pip_mgr = PiPManager(self)
        self.drop_mgr = DropManager(self)
        
        # --------------------------------------------------
        # 4. 建立 Layout 結構與 UI 組件
        # --------------------------------------------------
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

       # 1. 必須先初始化 Hotkey 管理器（供 sidebar 按鈕綁定使用）
        self.shortcut_mgr = self.hotkey_help_mgr  # 建立別名相容舊按鈕

        # 2. 之後才初始化 sidebar
        self.channel_mgr.init_sidebar()

        # 🎯 建立中央無級拉伸 Splitter 與頻道面板
        orientation = getattr(Qt.Orientation, 'Horizontal', getattr(Qt, 'Horizontal', None))
        self.main_splitter = CustomSplitter(orientation, self)
        self.main_splitter.setObjectName("main_splitter")
        self.main_splitter.setOpaqueResize(True)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(3)

        # 🎯 關鍵修正：將 Splitter 拖動信號直接綁定到控制欄調整函數，實現即時響應
        self.main_splitter.splitterMoved.connect(lambda pos, index: self._auto_adjust_bottom_controls())

        # 🎯 關鍵修正：直接抓取 Handle 實體物件，強制寫入樣式 (避開 Qt 原生繪製覆蓋)
        handle = self.main_splitter.handle(1)
        if handle:
            handle.setStyleSheet("""
                QWidget {
                    background-color: #8b5cf6 !important;  /* 常態：亮紫色 */
                    border: none !important;
                    image: none !important;                /* 🎯 強制抹除 Windows 原生灰色抓手紋理 */
                    border-radius: 3px;
                }
                QWidget:hover {
                    background-color: #00f2fe !important;  /* 滑鼠懸停：電光青色 */
                }
                QWidget:pressed {
                    background-color: #38ef7d !important;  /* 拖拽按下：螢光綠色 */
                }
            """)
         
        self.channel_mgr.init_channel_panel()
        if hasattr(self, 'channel_panel'):
            self.channel_panel.setMinimumWidth(300)  # 解鎖最小寬度，允許 1280x720 及 Win11 分屏無障礙拉伸
            self.channel_panel.setMaximumWidth(16777215)
            self.channel_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 建立播放區域
        self.init_player_area()
        
        # 建立右側 EPG 面板
        self.init_epg_panel()

        # 🎯 設定 Stretch Factor 權重，確保 Splitter 在 1280x720 或吸附分屏時可無級滑順拖拽至中間
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        if hasattr(self, 'epg_panel'):
            self.main_splitter.setStretchFactor(2, 0)

        self.main_layout.addWidget(self.main_splitter, 0)
        
        # --------------------------------------------------
        # 5. 套用主題、加載數據與快捷鍵
        # --------------------------------------------------
        saved_theme = self._settings.get("theme", "purple")
        self.current_theme = saved_theme
        self.skin_mgr.apply_skin(saved_theme)

        self.load_initialchannels() if hasattr(self, 'load_initialchannels') else self.load_initial_channels()

        if self.auto_play_last:
            last_url = self._settings.get("last_channel_url")
            if last_url:
                self.current_url = last_url
                self.current_channel_name = self._settings.get("last_channel_name", "上次觀看")
                self.channel_info.setText(f"[直播流] - {self.current_channel_name}")
                QTimer.singleShot(800, lambda: self.video_widget.play(last_url))
                
        # 滑鼠移動監聽
        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)
        
    # 📌 啟動時自動初始化，即刻在本地 epg_cache/ 目錄下生成空殼 epg_cache.db
        self.epg_db = EPGDatabase()
        
        # 喺 __init__ 最底部加上呢句，強制開機時進行一次 UI 狀態校正：
        self._update_bottom_control_bar_ui()
        
        #磨玻璃 iOS skin2
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _set_btn_svg_icon(self, btn, icon_name, icon_size=None):
        """為按鈕設定 SVG Icon，支援動態保持自定義尺寸"""
        # 1. 若有顯式傳入 icon_size，則更新按鈕尺寸
        if icon_size is not None:
            btn.setIconSize(icon_size)

        # 2. 獲取按鈕當前尺寸（若未設定過，預設為 18x18）
        cur_size = btn.iconSize()
        if cur_size.width() == 0 or cur_size.height() == 0:
            cur_size = QSize(18, 18)
            btn.setIconSize(cur_size)

        # 3. 根據當前尺寸渲染高畫質 SVG Icon
        icon = IconManager.get_icon(icon_name, size=cur_size.width())
        btn.setIcon(icon)

    def load_epg(self, epg_url):
        # 傳入 EPG 鏈接時觸發背景下載
        self.epg_worker = EPGDownloaderWorker(epg_url)
        self.epg_worker.finished_signal.connect(self.on_epg_download_finished)
        self.epg_worker.start()

    def on_epg_download_finished(self, success, msg):
        print(f"EPG 載入狀態: {msg}")
  
    def _do_real_seek(self):
        if self.pending_seek_target is not None:
            target_player = self.get_active_widget()
            if hasattr(target_player, 'seek'):
                target_player.seek(self.pending_seek_target)
            elif hasattr(target_player, 'mpv') and hasattr(target_player.mpv, 'command'):
                target_player.mpv.command('seek', self.pending_seek_target, 'absolute')
            self.pending_seek_target = None

    def get_active_widget(self):
        """獲取當前選中（焦點屏）嘅 MpvWidget"""
        if self.video_widgets and 0 <= self.active_player_index < len(self.video_widgets):
            return self.video_widgets[self.active_player_index]
        return self.video_widget

    def show_skin_menu(self):
        menu = RoundedMenu(self)
        menu.addAction("🟣 暗黑魅紫 (Default)", lambda: self.skin_mgr.apply_skin("purple"))
        menu.addAction("🔷 賽博霓藍", lambda: self.skin_mgr.apply_skin("cyan"))
        menu.addAction("🟢 翡翠極光", lambda: self.skin_mgr.apply_skin("emerald"))
        menu.addAction("🩶 鈦空深灰", lambda: self.skin_mgr.apply_skin("slate"))
        if self.btn_skin:
            menu.exec(self.btn_skin.mapToGlobal(QPoint(0, self.btn_skin.height())))

    def toggle_fullscreen(self):
        
        # 畫中畫模式下，絕對禁止切換全屏！
        if hasattr(self, 'pip_mgr') and self.pip_mgr.is_pip_mode:
            return
        
        if self.isFullScreen():
            self.bottom_bar.clearMask()
            self.bottom_bar.setWindowFlags(Qt.WindowType.Widget)
            self.bottom_bar.setMinimumSize(0, 0)
            self.bottom_bar.setMaximumSize(16777215, 16777215)
            self.bottom_bar.setFixedHeight(100)
            self.bottom_bar.setStyleSheet("")
            self.bottom_bar.setObjectName("bottom_bar")
            
            self.showNormal()
            self.sidebar.setVisible(True)
            self.channel_panel.setVisible(True)
            self.top_bar.setVisible(True)
            self.bottom_bar.setVisible(True)
            
            if hasattr(self, 'player_layout'):
                self.bottom_bar.setParent(None)
                self.player_layout.addWidget(self.bottom_bar)
            
            self.hide_timer.stop()
            self.unsetCursor()
            self.adjust_splitter_ratios()
        else:
            self.sidebar.setVisible(False)
            self.channel_panel.setVisible(False)
            self.top_bar.setVisible(False)
            
            self.bottom_bar.setParent(None)
            self.bottom_bar.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.bottom_bar.hide()
            self.showFullScreen()
            self.hide_timer.start()

        current = getattr(self, 'current_theme', 'purple')
        self.skin_mgr.apply_skin(current)

    def _show_controls(self):
        """全屏滑鼠移動時，喺螢幕最下方浮現統一主控制欄"""
        if self.isFullScreen():
            MARGIN_X = 40
            screen_geom = self.screen().geometry()
            vw = screen_geom.width() - (MARGIN_X * 2)
            bh = 100  
            OFFSET_Y = 30
            
            target_x = screen_geom.x() + MARGIN_X
            target_y = screen_geom.y() + screen_geom.height() - bh - OFFSET_Y
            
            self.bottom_bar.setFixedSize(vw, bh)
            self.bottom_bar.setGeometry(target_x, target_y, vw, bh)
            
            if hasattr(self, 'skin_mgr'):
                self.skin_mgr.apply_skin(self.current_theme)

            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, vw, bh), 12, 12)
            self.bottom_bar.setMask(QRegion(path.toFillPolygon().toPolygon()))
            
            self.bottom_bar.show()
            self.bottom_bar.raise_()
            self.unsetCursor()
            self.hide_timer.start()

    def hide_fullscreen_bars(self):
        if self.isFullScreen():
            self.bottom_bar.hide()
            self.top_bar.hide()
            self.setCursor(Qt.CursorShape.BlankCursor)

    def mouseMoveEvent(self, event):
        if self.isFullScreen():
            self._show_controls()
        super().mouseMoveEvent(event)

    def update_sidebar_btn_styles(self, active_btn):
        self.current_sidebar_btn = active_btn
        accent = self.current_theme_accent

        for btn in self.sidebar_btns:
            icon_name = btn.property("icon_name")
            is_active = (btn == active_btn)

            # 🎯 1. 切換 active 屬性並刷新 QSS 渲染
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

            # 🎯 2. 未選中圖示統一改為純白色 (#FFFFFF)
            if icon_name:
                color = accent if is_active else "#FFFFFF"
                icon = IconManager.get_icon(icon_name, color=color, size=22)
                btn.setIcon(icon)

    def start_parse_m3u(self, m3u_path_or_url):
        self.is_m3u_loading = True
        self.all_channels = []  # 🎯 1. 即時清空舊頻道數據
        
        # 🎯 2. 馬上觸發 UI 繪製，此時 is_m3u_loading 為 True，必定完美顯示「⏳ 正在加載...」
        if hasattr(self, 'channel_panel') and hasattr(self.channel_panel, 'render_channels'):
            self.channel_panel.render_channels()

        if hasattr(self, 'loading_bar'):
            self.loading_bar.setRange(0, 100)
            self.loading_bar.setValue(0)
            self.loading_bar.setVisible(True)
        if hasattr(self, 'channel_mgr'):
            self.channel_mgr.load_live_channels(reset=True)

        # 🎯 啟動前先檢查並安全回收正在運行的舊線程，防止新舊線程衝突或記憶體殘留
        if hasattr(self, 'm3u_worker') and self.m3u_worker and self.m3u_worker.isRunning():
            self.m3u_worker.quit()
            self.m3u_worker.wait(1000)

        self.m3u_worker = M3UFetchWorker(m3u_path_or_url)
        self.m3u_worker.finished_signal.connect(self.on_m3u_parsed)
        if hasattr(self.m3u_worker, 'progress_signal'):
            self.m3u_worker.progress_signal.connect(self.on_m3u_progress)
        
        # 1. 啟動線程
        self.m3u_worker.start()

        # 2. 🎯 關鍵修復：清空舊資料並【立即】強行觸發 UI 渲染，畫面即刻顯示「⏳ 正在加載...」
        self.all_channels = []
        if hasattr(self, 'channel_panel') and hasattr(self.channel_panel, 'render_channels'):
            self.channel_panel.render_channels()

    def on_m3u_progress(self, current, total):
        if hasattr(self, 'loading_bar') and total > 0:
            self.loading_bar.setMaximum(total)
            self.loading_bar.setValue(current)

    def on_m3u_parsed(self, *args, **kwargs):
        """當 M3U 解析完成時觸發，全安全防護渲染頻道列表與隱藏遮罩，並啟動 EPG 載入"""
        channels = args[0] if args else kwargs.get('channels', [])
        epg_url = args[1] if len(args) > 1 else kwargs.get('epg_url', '')

        self.is_m3u_loading = False
        if hasattr(self, 'loading_bar'):
            self.loading_bar.setVisible(False)

        # 寫入主視窗核心快取
        self.all_channels_data = channels

        print(f"📦 [DEBUG] M3U 解析完成，收到 {len(channels) if isinstance(channels, list) else 0} 個頻道，EPG 網址: '{epg_url}'")

        if hasattr(self, 'channel_mgr') and self.channel_mgr:
            mgr = self.channel_mgr

            # 1. 寫入頻道資料到管理對象的所有可能屬性
            for attr in ['channels', 'all_channels', 'raw_channels', '_channels']:
                setattr(mgr, attr, channels)

            # 2. 優先調用 ChannelPanelManager 的 UI 刷新與載入函數
            if hasattr(mgr, 'load_live_channels') and callable(mgr.load_live_channels):
                try:
                    mgr.load_live_channels(reset=True)
                    print("✅ [DEBUG] 已執行 mgr.load_live_channels(reset=True)")
                except Exception as e:
                    print(f"⚠️ [DEBUG] 執行 load_live_channels 失敗: {e}")

            if hasattr(mgr, 'refresh_channel_list') and callable(mgr.refresh_channel_list):
                try:
                    mgr.refresh_channel_list()
                    print("✅ [DEBUG] 已執行 mgr.refresh_channel_list()")
                except Exception as e:
                    print(f"⚠️ [DEBUG] 執行 refresh_channel_list 失敗: {e}")

            # 3. 安全獲取實體 QWidget 容器並進行遮罩清理 (使用 PyQt6 正確導入)
            search_targets = [mgr]
            for widget_attr in ['widget', 'panel', 'ui', 'view', 'container', 'main_widget']:
                if hasattr(mgr, widget_attr) and getattr(mgr, widget_attr):
                    search_targets.append(getattr(mgr, widget_attr))

            for target in search_targets:
                if hasattr(target, 'findChildren'):
                    try:
                        from PyQt6.QtWidgets import QWidget, QFrame, QLabel
                        for child in target.findChildren(QWidget):
                            text_content = ""
                            if isinstance(child, QLabel) or hasattr(child, 'text'):
                                text_content = str(child.text())
                            
                            obj_name = child.objectName().lower() if hasattr(child, 'objectName') else ""
                            
                            if "正在加載" in text_content or "請稍候" in text_content or "loading" in obj_name:
                                child.hide()
                                child.setVisible(False)
                                parent = child.parentWidget()
                                if parent and parent not in search_targets and isinstance(parent, (QFrame, QWidget)):
                                    parent.hide()
                                    parent.setVisible(False)
                                print(f"🙈 [DEBUG] 成功隱藏加載卡片: {child}")
                    except Exception as e:
                        print(f"⚠️ [DEBUG] 掃描隱藏卡片防護捕捉: {e}")

        # 4. 觸發 EPG 自動下載
        setting_epg = ""
        if hasattr(self, '_settings') and isinstance(self._settings, dict):
            setting_epg = self._settings.get("epg_url", "") or self._settings.get("current_epg_url", "")
        
        target_epg_url = setting_epg or epg_url

        if target_epg_url and hasattr(self, 'channel_mgr'):
            print(f"💡 [DEBUG] 成功獲取 EPG 網址 (來源: {'設定檔' if setting_epg else 'M3U標頭'}): {target_epg_url}")
            self.channel_mgr.load_epg_data(target_epg_url)
        else:
            print(f"⚠️ [DEBUG] M3U 標頭無 EPG 且設定檔為空，跳過 EPG 載入 (當前 epg_url='{epg_url}')")

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

        # 強制維持與 channel_panel.py 一致的透明背景與 Hover 圓角
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

        # 優先呼叫 _set_btn_svg_icon 統一切換圖示（與開機載入對齊）
        if hasattr(self, '_set_btn_svg_icon'):
            self._set_btn_svg_icon(star_btn, "star_filled" if new_state else "star_outline")
        elif IconManager:
            star_color = "#f59e0b" if new_state else "#64748b"
            star_icon = IconManager.get_icon("star", color=star_color, size=18)
            star_btn.setIcon(star_icon)
            star_btn.setIconSize(QSize(18, 18))

        self._settings["favorites_list"] = self.favorites_list
        _save_settings(self._settings)

    def on_channel_scroll(self, value):
        scrollbar = self.channel_list.verticalScrollBar()
        if scrollbar.maximum() > 0 and value >= scrollbar.maximum() * 0.70:
            self.channel_mgr.load_live_channels(reset=False)

    def set_quality_filter(self, filter_text, active_btn):
        self.current_quality = filter_text
        accent = self.current_theme_accent
        for btn in self.filter_btn_list:
            if btn == active_btn:
                btn.setStyleSheet(f"background-color: {accent}; color: white; border-radius: 12px; padding: 5px; font-size: 12px;")
            else:
                btn.setStyleSheet("background-color: transparent; color: #888; border: 1px solid #2a2a35; border-radius: 12px; padding: 5px; font-size: 12px;")
        self.channel_mgr.load_live_channels(reset=True)
   
    def _esc_handler(self):
        if self.isFullScreen():
            self.toggle_fullscreen()

    def _volume_up(self):
        new_val = min(100, self.vol_slider.value() + 5)
        self.vol_slider.setValue(new_val)
        self.set_volume(new_val)

    def _volume_down(self):
        new_val = max(0, self.vol_slider.value() - 5)
        self.vol_slider.setValue(new_val)
        self.set_volume(new_val)

    def toggle_hw(self):
        self.hw_enabled = not self.hw_enabled
        active_w = self.get_active_widget()
        active_w.hw_enabled = self.hw_enabled
        self._update_hw_btn_style()   # <-- 刪咗 'accent'
        active_w._set_property_string("hwdec", "auto" if self.hw_enabled else "no")
        self._settings["hwdec"] = self.hw_enabled
        _save_settings(self._settings)
        
    def _update_hw_btn_style(self):
        """HW On = 背景變 accent 色永久停留；HW Off = 恢復普通 menu_btn"""
        accent = getattr(self, 'current_theme_accent', '#8529ff')
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
            # 清空 inline stylesheet，交返畀 skin.py 嘅 [role="menu_btn"] 規則
            self.btn_hw.setStyleSheet("")
            self.btn_hw.setToolTip("HW: Off")
        
        self.btn_hw.style().unpolish(self.btn_hw)
        self.btn_hw.style().polish(self.btn_hw)
        self.btn_hw.update()
        
    # ========== 播放器區域 ==========
    def init_player_area(self):
        player_panel = QWidget()
        player_panel.setObjectName("player_panel")
        player_panel.setMinimumWidth(200)  # 解鎖最小寬度
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
        menu_btn.setObjectName("btn_menu_toggle")  # 🎯 綁定 skin.py 的 ID 選擇器
        menu_btn.setFixedSize(46, 42)
        menu_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        menu_btn.setToolTip("開關頻道列表")
        menu_btn.clicked.connect(self.toggle_channel_panel)
        self._set_btn_svg_icon(menu_btn, "menu", QSize(36, 36))
        
        self.channel_info = QLabel("[直播流] - 請點擊左側頻道播放")
        self.channel_info.setStyleSheet("color: #ccc; font-size: 20px; background: transparent;")

        # 🎯 右側頂部欄新增【📋 節目表】按鈕
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

            w = MpvEmbedWidget()
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
        # 🎯 關鍵修正：限制中間播放器面板最小寬度為 500px (防止被拖拽壓成縫隙)
        player_panel.setMinimumWidth(500)
        self.screen_mgr.set_screen_layout(1)
        
    # --------------------------------------------------
    # 🎯 右側 EPG 節目表面板與 Windows 吸附適配
    # --------------------------------------------------
    def init_epg_panel(self):
        """初始化右側 EPG 節目表 Splitter 面板"""
        self.epg_panel = EPGPanelWidget(self)
        self.main_splitter.addWidget(self.epg_panel)
        self.epg_panel.setVisible(False)  # 預設隱藏

    def toggle_epg_panel(self):
        """切換右側 EPG 節目表顯示狀態"""
        if hasattr(self, 'epg_panel'):
            self.epg_panel.toggle_panel()

    def update_epg_content(self, channel_name=None):
        """更新 EPG 節目表內容"""
        if hasattr(self, 'epg_panel'):
            self.epg_panel.update_epg_content(channel_name)
            
    def adjust_splitter_ratios(self):
        """🎯 適應 1280x720 視窗與 Windows 11 磁吸附分屏動態拉伸比例"""
        total_w = self.main_splitter.width()
        if total_w <= 0:
            return

        # 僅在初次初始化或顯示切換時給予建議寬度，保留滑動條自主拖拽空間
        if not hasattr(self, '_splitter_initialized'):
            self._splitter_initialized = True
            left_w = 240 if self.channel_panel.isVisible() else 0
            right_w = 220 if (hasattr(self, 'epg_panel') and self.epg_panel.isVisible()) else 0
            
            if total_w <= 1280:
                left_w = 200 if left_w > 0 else 0
                right_w = 180 if right_w > 0 else 0

            center_w = total_w - left_w - right_w
            sizes = [left_w, center_w]
            if hasattr(self, 'epg_panel') and self.epg_panel.isVisible():
                sizes.append(right_w)
            self.main_splitter.setSizes(sizes)

    def resizeEvent(self, event):
        """視窗拉動大小時觸發"""
        super().resizeEvent(event)
        self._auto_adjust_bottom_controls()
    
        # 🎯 喺 _auto_adjust_bottom_controls 的正上方插入以下這個新函數：
    def showEvent(self, event):
        """視窗第一次顯示時觸發"""
        super().showEvent(event)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self._auto_adjust_bottom_controls)
        
    def _auto_adjust_bottom_controls(self):
        
        if hasattr(self, 'bottom_bar') and hasattr(self.bottom_bar, 'auto_adjust_controls'):
            self.bottom_bar.auto_adjust_controls()
            
    # ========== 多屏邏輯 ==========
    def show_screen_layout_menu(self):
        menu = RoundedMenu(self)
        menu.addAction("單屏模式 (標準)", lambda: self.screen_mgr.set_screen_layout(1))
        menu.addAction("雙屏模式 (左右)", lambda: self.screen_mgr.set_screen_layout(2))
        menu.addAction("三屏模式 (1:2)", lambda: self.screen_mgr.set_screen_layout(3))
        menu.addAction("四屏模式 (田字)", lambda: self.screen_mgr.set_screen_layout(4))
        
        if self.btn_screen_layout:
            menu.exec(self.btn_screen_layout.mapToGlobal(QPoint(0, self.btn_screen_layout.height())))

    def _event_filter_install_for_widgets(self):
        widgets = self.video_widgets or self.video_frames
        for w in widgets:
            w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            try:
                w.customContextMenuRequested.disconnect()
            except Exception:
                pass
            w.customContextMenuRequested.connect(lambda pos, target=w: self.screen_mgr._show_context_menu_for_widget(pos, target))

    def _close_single_widget(self, widget):
        try:
            if hasattr(widget, 'stop'):
                widget.stop()
            elif hasattr(widget, 'mpv') and hasattr(widget.mpv, 'command'):
                widget.mpv.command('stop')
        except Exception as e:
            print(f"關閉窗口異常: {e}")

        widget.has_media = False
        widget.update()
        self.screen_mgr._sync_audio_focus()

    # ========== 全局點擊與亮框連動 ==========
    def eventFilter(self, watched, event):
        """事件過濾器：解決 MPV 原生窗口蓋頂導致無法拖動與點擊穿透問題"""
        if watched == getattr(self, 'video_widget', None) and getattr(self, 'is_pip_mode', False):
            # 1. 鼠標按下：計算拖動起始偏移量（避開按鈕與縮放角）
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                pos = event.pos()
                btn_hit = (
                    hasattr(self, 'btn_restore_pip') 
                    and self.btn_restore_pip.isVisible() 
                    and self.btn_restore_pip.geometry().contains(pos)
                )
                grip_hit = (
                    hasattr(self, 'sizegrip_pip') 
                    and self.sizegrip_pip.isVisible() 
                    and self.sizegrip_pip.geometry().contains(pos)
                )

                if not btn_hit and not grip_hit:
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True  # 縮排需在 def eventFilter 內部

            # 2. 鼠標移動：執行視窗位移
            elif event.type() == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
                if hasattr(self, '_drag_pos') and self._drag_pos is not None:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True

            # 3. 鼠標釋放：清除拖動狀態
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_pos = None

        return super().eventFilter(watched, event)

    def _on_screen_clicked(self, idx):
        self.active_player_index = idx
        self.video_widget = self.video_widgets[self.active_player_index]
        
        self.screen_mgr.update_screen_borders()
        self.screen_mgr._sync_audio_focus()
        self._update_bottom_control_bar_ui()
        self.sync_controls_ui()

    def _update_bottom_control_bar_ui(self):
        """根據當前選中分屏，動態更新主控制欄 UI"""
        active_w = self.get_active_widget()
        
        # 🎯 未載入媒體時，鎖定顯示 play
        if not active_w or not getattr(active_w, 'has_media', False):
            self.play_btn.setText("")
            self._set_btn_svg_icon(self.play_btn, "play")
            return

        try:
            # 🎯 根據播放器組件真實的 is_paused 狀態更新按鈕
            is_paused = getattr(active_w, 'is_paused', True)
            icon_name = "play" if is_paused else "pause"

            self.play_btn.setText("")
            self._set_btn_svg_icon(self.play_btn, icon_name)

            cur_vol = active_w.get_volume() if hasattr(active_w, 'get_volume') else 100
            self.vol_slider.blockSignals(True)
            self.vol_slider.setValue(int(cur_vol if cur_vol is not None else 100))
            self.vol_slider.blockSignals(False)
        except Exception:
            pass

    def sync_controls_ui(self):
        """統一同步底部控制欄 UI"""
        self._update_bottom_control_bar_ui()
        active_w = self.get_active_widget()
        if not active_w:
            return

        is_muted = active_w.get_mute()
        vol = active_w.get_volume()

        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(int(vol))
        self.vol_slider.blockSignals(False)
        
        self._set_btn_svg_icon(self.btn_mute, "mute" if (is_muted or vol == 0) else "volume")

    def toggle_mute(self):
        active_w = self.get_active_widget()
        if not active_w:
            return

        current_mute = active_w.get_mute()
        active_w.set_mute(not current_mute)
        self.sync_controls_ui()

    def set_volume(self, value):
        active_w = self.get_active_widget()
        if not active_w:
            return

        active_w.set_volume(value)
        is_muted = active_w.get_mute()
        
        self._set_btn_svg_icon(self.btn_mute, "mute" if (value == 0 or is_muted) else "volume")

    # ========== 播放控制（指向 active屏） ==========
    def play_channel(self, item):
        url = None
        ch_name = ""
        ch_obj = {}

        # 1. 嘗試從 UserRole 或 字典提取數據
        if hasattr(item, 'data'):
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

        # 2. 🎯 核心修復：使用 item.listWidget() 並跳過 Logo Emoji Label
        if not ch_name and hasattr(item, 'listWidget'):
            lw = item.listWidget()
            if lw:
                w = lw.itemWidget(item)
                if w:
                    from PyQt6.QtWidgets import QLabel
                    labels = w.findChildren(QLabel)
                    ignore_symbols = {"📺", "⭐", "☆", "🕒"}
                    for lbl in labels:
                        txt = lbl.text().strip()
                        if txt and not txt.isdigit() and txt not in ignore_symbols:
                            ch_name = txt
                            break

        # 3. 備用：若依然拿不到，嘗試 item.text()
        if not ch_name and hasattr(item, 'text') and item.text():
            ch_name = item.text()

        if not ch_name:
            ch_name = "未知頻道"

        if not url:
            return

        self.current_url = url
        self.current_channel_name = ch_name
        self.current_channel_obj = ch_obj if isinstance(ch_obj, dict) else {'name': ch_name, 'url': url}
        self.channel_info.setText(f"[直播流] - {ch_name}")

        target_widget = self.get_active_widget()

        target_widget.has_media = True
        target_widget.play(url)

        self.screen_mgr._sync_audio_focus()
        QTimer.singleShot(300, self.screen_mgr._sync_audio_focus)

        # 🎯 4. 新增播放歷史紀錄 (去重置頂並持久化儲存)
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
        if hasattr(self, 'epg_panel') and self.epg_panel.isVisible():
            self.update_epg_content()

    def toggle_play(self):
        active_w = self.get_active_widget()
        if active_w.is_paused:
            active_w.resume()
            
            self._set_btn_svg_icon(self.play_btn, "pause")
        else:
            active_w.pause()
            
            self._set_btn_svg_icon(self.play_btn, "play")

    def stop_play(self):
        active_w = self.get_active_widget()
        if active_w:
            active_w._set_property_string("time-pos", "0")
            active_w.pause()
            
            self._set_btn_svg_icon(self.play_btn, "play")
            self.lbl_current_time.setText("00:00")
            self.seek_slider.setValue(0)

    def seek_offset(self, offset_sec):
        """快捷鍵相對尋道 (極簡生產環境版)"""
        target_player = self.get_active_widget()
        if target_player and hasattr(target_player, 'mpv') and target_player.mpv:
            try:
                target_player.mpv.command("seek", offset_sec, "relative+exact")
            except Exception:
                pass

    def on_seek_pressed(self):
        self.is_seeking = True

    def on_seek_released(self):
        val = self.seek_slider.value()
        target_player = self.get_active_widget()
        
        duration = 0
        if hasattr(target_player, 'get_duration'):
            duration = target_player.get_duration()
        elif hasattr(target_player, 'duration'):
            duration = target_player.duration
            
        if duration > 0:
            target_pos = (val / 1000.0) * duration
            self.pending_seek_target = target_pos
            self.seek_debounce_timer.start(300)
            
        self.is_seeking = False

    # ========== 菜單邏輯（指向 active屏） ==========
    def show_aspect_menu(self):
        menu = RoundedMenu(self)
        active_w = self.get_active_widget()
        ratios = [("預設 (原始)", None), ("16:9", "16:9"), ("4:3", "4:3"), ("填滿畫面", "-1")]
        for label, ratio in ratios:
            action = QAction(label, self)
            action.triggered.connect(lambda _, r=ratio, w=active_w: w.set_aspect(r))
            menu.addAction(action)
        menu.exec(self.btn_aspect.mapToGlobal(self.btn_aspect.rect().bottomLeft()))

    def show_audio_menu(self):
        menu = RoundedMenu(self)
        active_w = self.get_active_widget()
        track_json = active_w.get_property_string("track-list")
        current_aid = active_w.get_property_string("aid") or "no"
        
        if not track_json:
            menu.addAction(QAction("無可用音軌", self))
            menu.exec(self.btn_audio.mapToGlobal(self.btn_audio.rect().bottomLeft()))
            return
        
        try:
            tracks = json.loads(track_json)
            audio_tracks = [t for t in tracks if t.get("type") == "audio"]
            if not audio_tracks:
                menu.addAction(QAction("無可用音軌", self))
            else:
                for t in audio_tracks:
                    tid = str(t.get("id", ""))
                    ttitle = t.get("title", "") or t.get("lang", "") or f"音軌 {tid}"
                    label = f"{'✓ ' if tid == current_aid else ''}{ttitle}"
                    action = QAction(label, self)
                    action.triggered.connect(lambda _, id=tid, w=active_w: w._set_property_string("aid", id))
                    menu.addAction(action)
        except Exception:
            menu.addAction(QAction("無可用音軌", self))

        menu.exec(self.btn_audio.mapToGlobal(self.btn_audio.rect().bottomLeft()))

    def show_subtitle_menu(self):
        menu = RoundedMenu(self)
        active_w = self.get_active_widget()
        track_json = active_w.get_property_string("track-list")
        current_sid = active_w.get_property_string("sid") or "no"
        
        if not track_json:
            menu.addAction(QAction("無可用字幕", self))
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
                    label = f"{'✓ ' if tid == current_sid else ''}{ttitle}"
                    action = QAction(label, self)
                    action.triggered.connect(lambda _, id=tid, w=active_w: w._set_property_string("sid", id))
                    menu.addAction(action)
                
                menu.addSeparator()
                off = QAction("❌ 關閉字幕", self)
                off.triggered.connect(lambda w=active_w: w._set_property_string("sid", "no"))
                menu.addAction(off)
        except Exception:
            menu.addAction(QAction("無可用字幕", self))

        menu.exec(self.btn_sub.mapToGlobal(self.btn_sub.rect().bottomLeft()))

    def take_snapshot(self):
        active_w = self.get_active_widget()
        try:
            # 直接呼叫底層，強制由 player_engine 統一寫入 snapshots 資料夾
            success = active_w.screenshot()
            if success:
                if hasattr(self, 'tip_label') and self.tip_label:
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

    # ========== 定時器更新 UI（跟隨 active屏） ==========
    def update_ui_timer(self):
        active_w = self.get_active_widget()
        if not active_w or not active_w.mpv:
            return

        try:
            duration = active_w.get_duration()
            pos = active_w.get_time_pos()

            if duration and duration > 0:
                if not self.is_seeking:
                    self.seek_slider.setValue(int((pos / duration) * 1000))
                self.lbl_current_time.setText(self.format_time(int(pos * 1000)))
                self.lbl_total_time.setText(self.format_time(int(duration * 1000)))
                self.seek_slider.setEnabled(True)
            else:
                self.lbl_current_time.setText("00:00")
                self.lbl_total_time.setText("00:00")
                self.seek_slider.setValue(0)
                self.seek_slider.setEnabled(False)

            self._update_bottom_control_bar_ui()
        except Exception:
            pass

    @staticmethod
    def format_time(ms):
        if ms < 0:
            return "00:00"
        seconds = int(ms / 1000)
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    # ========== 對話框與面板事件 ==========
    def toggle_channel_panel(self):
        """切換左側頻道選單顯示狀態"""
        if not hasattr(self, 'channel_panel') or self.channel_panel is None:
            return

        is_visible = self.channel_panel.isVisible()
        self.channel_panel.setVisible(not is_visible)
        
        if hasattr(self, 'adjust_splitter_ratios'):
            self.adjust_splitter_ratios()

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(20, self._auto_adjust_bottom_controls)

    def load_initial_channels(self):
        target_url = self._settings.get("current_m3u_url") if isinstance(self._settings, dict) else None
        
        if not target_url and hasattr(self, 'current_m3u_url'):
            target_url = self.current_m3u_url
            
        if not target_url and self.m3u_sources:
            target_url = self.m3u_sources[0]['url']

        # 1. 開始讀取/下載 M3U 檔案
        if target_url:
            self.start_parse_m3u(target_url)

        # 📌 不管有沒有網址，都強制呼叫！讓外送員出來印 Log 報告狀態
        epg_url = self._settings.get("epg_url", "") or self._settings.get("current_epg_url", "")
        if hasattr(self, 'channel_mgr'):
            print(f"🔍 [DEBUG] 正在準備啟動 EPG，從設定檔讀取到的網址為: '{epg_url}'")
            self.channel_mgr.load_epg_data(epg_url)
            
            
    def _on_m3u_loaded(self, *args, **kwargs):
        """當 M3U 解析完成時的回調函數 (同時相容 on_m3u_parsed)"""
        channels = args[0] if args else kwargs.get('channels', [])
        epg_url = args[1] if len(args) > 1 else kwargs.get('epg_url', '')

        self.is_m3u_loading = False
        if hasattr(self, 'loading_bar'):
            self.loading_bar.setVisible(False)

        print(f"📦 [DEBUG] M3U 解析完成！收到 {len(channels) if isinstance(channels, list) else 0} 個頻道，EPG 網址: '{epg_url}'")

        # 1. 寫入主視窗核心屬性 (這步最關鍵，channel_panel 靠這個渲染列表)
        self.all_channels_data = channels

        # 2. 同步資料給 channel_mgr 並觸發 QListWidget 渲染
        if hasattr(self, 'channel_mgr') and self.channel_mgr:
            mgr = self.channel_mgr
            setattr(mgr, 'channels', channels)
            setattr(mgr, 'all_channels', channels)

            # 傳入 reset=True 讓 channel_panel 重新計算過濾快取並把「正在加載」告示牌替換為頻道
            if hasattr(mgr, 'load_live_channels') and callable(mgr.load_live_channels):
                try:
                    mgr.load_live_channels(reset=True)
                    print("🎉 [DEBUG] 成功觸發 mgr.load_live_channels(reset=True)")
                except Exception as e:
                    print(f"⚠️ [DEBUG] 執行 load_live_channels 失敗: {e}")

        # 3. 觸發 EPG 下載
        setting_epg = ""
        if hasattr(self, '_settings') and isinstance(self._settings, dict):
            setting_epg = self._settings.get("epg_url", "") or self._settings.get("current_epg_url", "")

        target_epg_url = setting_epg or epg_url

        if target_epg_url and hasattr(self, 'channel_mgr'):
            print(f"💡 [DEBUG] 成功獲取 EPG 網址: {target_epg_url}")
            self.channel_mgr.load_epg_data(target_epg_url)

    # 📌 防護別名：讓 connect(self.on_m3u_parsed) 與 connect(self._on_m3u_loaded) 都能成功綁定不報錯
    on_m3u_parsed = _on_m3u_loaded
    
    # [前一行]     on_m3u_parsed = _on_m3u_loaded
    def toggle_pip(self):
        """畫中畫 (PiP) 模式切換邏輯"""
        self.pip_mgr.toggle()
