#channel_panel.py
import re
from config import *  # 匯入配置
from datetime import datetime
from widgets import RoundedMenu  # 引入自訂圓角選單

#=============================================================================================
def natural_sort_key(s):
    """自然排序：將文字中的數字拆解為整數 (解決 EP1 < EP2 < EP10 排序混亂問題)"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

try:
    from skin import IconManager  # 引入 SVG 圖示管理器
except ImportError:
    IconManager = None

#=============================================================================================

def get_rounded_pixmap(pixmap: QPixmap, target_size: QSize, radius: int = 5) -> QPixmap:
    """
    🎯 保持長寬比高質量縮放 + 圓角 (R角) 裁切
    徹底解決台標圖片擠壓變形與直角邊角穿透問題
    """
    if pixmap.isNull():
        return pixmap

    scaled_pixmap = pixmap.scaled(
        target_size, 
        Qt.AspectRatioMode.KeepAspectRatio, 
        Qt.TransformationMode.SmoothTransformation
    )

    out_pixmap = QPixmap(scaled_pixmap.size())
    out_pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(out_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    path = QPainterPath()
    path.addRoundedRect(0.0, 0.0, float(scaled_pixmap.width()), float(scaled_pixmap.height()), float(radius), float(radius))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled_pixmap)
    painter.end()

    return out_pixmap
    
#=============================================================================================

def _clean_epg_key(text):
    """強效清理頻道名稱：轉小寫、去除畫質標記 (HD/4K/FHD) 與所有非英數中文字元"""
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r'(4k|fhd|hd|sd|hevc|60fps|頻道|台)', '', text)
    text = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text)
    return text.strip()
        
#=============================================================================================

class LogoFetchThread(QThread):
    """背景非同步下載台標線程，完全不霸佔 UI 主線程"""
    finished_signal = pyqtSignal(str, object)

    def __init__(self, url, path, box):
        super().__init__()
        self.url = url
        self.path = path
        self.box = box

    def run(self):
        try:
            import urllib.parse, urllib.request
            safe_url = urllib.parse.quote(self.url, safe=':/?&=#%')
            req = urllib.request.Request(safe_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = resp.read()
                with open(self.path, "wb") as f:
                    f.write(data)
                self.finished_signal.emit(self.path, self.box)
        except Exception:
            pass

#=============================================================================================

class ChannelPanelManager:  # 面板管理器
    def __init__(self, main_window):  # 初始化
        self.win = main_window  # 綁定主視窗
    
    # ========== 側邊欄 ==========
    def init_sidebar(self):
        self.win.sidebar = QWidget()  # 初始化側邊欄
        self.win.sidebar.setObjectName("sidebar")  # 設定組件名稱
        self.win.sidebar.setFixedWidth(60)  # 設定固定寬度

        layout = QVBoxLayout(self.win.sidebar)  # 建立垂直佈局
        layout.setContentsMargins(0, 10, 0, 10)  # 設定邊距
        layout.setSpacing(8)  # 設定空格

        logo = QPushButton("K20")  # 建立標誌按鈕
        logo.setObjectName("sidebar_logo")  # 設定標誌名稱
        layout.addWidget(logo)  # 加入佈局

        self.win.sidebar_btns = []  # 按鈕列表
        
        # 🎯 1. 視圖切換按鈕列表 (SVG圖示名, 提示文字, 模式標籤)
        view_buttons = [
            ("tv", "直播頻道", "live"),
            ("star", "我的收藏", "fav"),
            ("folder", "最近播放", "history"),
            ("film", "本地媒體", "local")  # 👈 新增：本地媒體播放列表按鈕
        ]
        
        for icon_name, tip, mode in view_buttons:
            btn = QPushButton("")  # 列表管理按鈕
            btn.setToolTip(tip)  # 設定工具提示
            btn.setProperty("icon_name", icon_name)  # 綁定圖示名稱
            btn.setIconSize(QSize(50, 50))  # 設定Icon大小
            btn.clicked.connect(lambda checked, b=btn, m=mode: self.switch_channel_view(m, b))  # 綁定切換模式
            self.win.sidebar_btns.append(btn)  # 存入列表
            layout.addWidget(btn)  # 加入佈局
            
        # 🎯 2. 工具功能按鈕列表 (SVG圖示名, 提示文字, 觸發函數)
        action_buttons = [
            ("m3u", "訂閱列表管理", self.win.shortcut_mgr.open_m3u_manager),
            ("help", "快捷說明", self.win.shortcut_mgr.open_help_dialog)
        ]
        
        for icon_name, tip, slot in action_buttons:
            btn = QPushButton("")  # 列表管理按鈕
            btn.setToolTip(tip)  # 設定提示
            btn.setProperty("icon_name", icon_name)  # 綁定圖示名稱
            btn.setIconSize(QSize(50, 50))  # 設定Icon大小
            btn.clicked.connect(slot) # 綁定點擊事件槽
            self.win.sidebar_btns.append(btn)  # 存入列表
            layout.addWidget(btn)  # 加入佈局

        layout.addStretch()  # 加入彈性空間
        
        # 🎯 3. 底部系統設定按鈕
        setting_btn = QPushButton("")  # 🧽 清空 Emoji
        setting_btn.setToolTip("系統設置")  # 設定提示
        setting_btn.setObjectName("setting_btn")  # 設定名稱
        setting_btn.setProperty("icon_name", "gear")  # 綁定圖示名稱
        setting_btn.setIconSize(QSize(50, 50))  # 設定Icon大小
        setting_btn.clicked.connect(self.win.shortcut_mgr.open_settings_dialog)  # 綁定打開說明
        self.win.sidebar_btns.append(setting_btn)  # 存入列表
        layout.addWidget(setting_btn)  # 加入佈局
        
        # 🎯 4. 預設高亮首鈕
        if self.win.sidebar_btns:
            self.win.update_sidebar_btn_styles(self.win.sidebar_btns[0])
            
        # 🎯 5. 側邊欄加入佈局
        self.win.main_layout.addWidget(self.win.sidebar)
            
#=============================================================================================
    
    def show_group_menu(self):  # 顯示分組選單
        menu = RoundedMenu(self.win)  # 建立圓角選單
        
        # 使用 dict.fromkeys 保留原始順序並快速去重
        raw_groups = [ch.get('group', '未分類') or '未分類' for ch in self.win.all_channels_data if isinstance(ch, dict)]
        groups = ["全部分組"] + list(dict.fromkeys(raw_groups))

        for g_name in groups:
            action = QAction(g_name, self.win)
            action.triggered.connect(lambda _, name=g_name: self.filter_by_group(name))
            menu.addAction(action)

        if hasattr(self.win, 'btn_group_menu'):
            menu.exec(self.win.btn_group_menu.mapToGlobal(QPoint(0, self.win.btn_group_menu.height())))
            
#=============================================================================================
    
    def filter_by_group(self, group_name):  # 執行分組過濾
        self.win.current_group_filter = group_name
        display_text = group_name if len(group_name) <= 8 else group_name[:7] + "…"
        self.win.btn_group_menu.setText(f"{display_text} ▾")
        self.load_live_channels(reset=True)
        
#=============================================================================================
    
    def show_sort_menu(self):  # 顯示排序選單
        menu = RoundedMenu(self.win)
        sort_options = [
            ("default", "預設排序"),
            ("latency_asc", "低延遲優先 ⚡"),
            ("name_asc", "名稱 A-Z"),
            ("name_desc", "名稱 Z-A")
        ]
        
        for mode_id, mode_label in sort_options:
            action = QAction(mode_label, self.win)
            action.triggered.connect(lambda _, m=mode_id, l=mode_label: self.set_sort_mode(m, l))
            menu.addAction(action)

        menu.exec(self.win.btn_sort_menu.mapToGlobal(QPoint(0, self.win.btn_sort_menu.height())))
    
#=============================================================================================
    
    def set_sort_mode(self, mode, label):  # 設定排序模式
        self.win.current_sort_mode = mode
        self.win.btn_sort_menu.setText(f"{label} ▾")
        
        # 🎯 判斷當前頁面：若在直播頁面就刷直播，若在本地媒體/歷史紀錄就刷對應頁面
        current_view = self.win.channel_list_mode
        if current_view == 'live':
            self.load_live_channels(reset=True)
        else:
            self.switch_channel_view(current_view)
            
#=============================================================================================
    
    def toggle_ping_test(self):  # 開關測速
        if getattr(self, 'is_pinging', False):
            self.is_pinging = False
            if hasattr(self, 'ping_worker') and self.ping_worker.isRunning():
                self.ping_worker.is_stopped = True
                self.ping_worker.quit()
                self.ping_worker.wait(1000)
            self.win.btn_ping_test.setText("⚡ 測速")
            return

        if not hasattr(self.win, 'filtered_channels_cache') or not self.win.filtered_channels_cache:
            return

        self.is_pinging = True
        self.win.btn_ping_test.setText("🛑 停止")
        
        if not hasattr(self.win, 'channel_latencies'):
            self.win.channel_latencies = {}

        class PingWorker(QThread):
            progress = pyqtSignal(str, int)
            finished_signal = pyqtSignal()

            def __init__(self, channels):
                super().__init__()
                self.channels = channels
                self.is_stopped = False

            def run(self):
                for ch in self.channels:
                    if self.is_stopped:
                        break
                    url = ch.get('url', '')
                    if not url or not url.startswith('http'):
                        continue
                    start = time.time()
                    try:
                        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=2.5):
                            ms = int((time.time() - start) * 1000)
                            if not self.is_stopped:
                                self.progress.emit(url, ms)
                    except Exception:
                        if not self.is_stopped:
                            self.progress.emit(url, -1)
                self.finished_signal.emit()
        
        def _on_ping_update(url, ms):
            self.win.channel_latencies[url] = ms
            for idx in range(self.win.channel_list.count()):
                item = self.win.channel_list.item(idx)
                if item and item.data(Qt.ItemDataRole.UserRole) == url:
                    widget = self.win.channel_list.itemWidget(item)
                    if widget:
                        self.update_latency_badge(widget, ms)
                    break  # 🎯 關鍵優化：搵到即停，唔再盲搗全列表！
        
        def _on_ping_finished():
            self.is_pinging = False
            self.win.btn_ping_test.setText("⚡ 測速")
            if hasattr(self, 'ping_worker'):
                self.ping_worker.quit()
                self.ping_worker.wait(500)  # 🎯 確保線程完全終止
                self.ping_worker.deleteLater()
                self.ping_worker = None      # 🎯 徹底釋放資源
        
        self.ping_worker = PingWorker(self.win.filtered_channels_cache)
        self.ping_worker.progress.connect(_on_ping_update)
        self.ping_worker.finished_signal.connect(_on_ping_finished)
        self.ping_worker.start()
    
#============================================================================================= 
   
    def update_latency_badge(self, item_widget, ms):
        badge = item_widget.findChild(QLabel, "latency_badge")
        if not badge:
            badge = QLabel()
            badge.setObjectName("latency_badge")
            badge.setFixedHeight(22)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout = item_widget.layout()
            layout.insertWidget(layout.count() - 1, badge)

        if ms < 0 or ms >= 800:
            bg_color = "#ef4444"
            text = "FAIL" if ms < 0 else f"{ms}ms"
        elif 300 <= ms <= 799:
            bg_color = "#f59e0b"
            text = f"{ms}ms"
        else:
            bg_color = "#10b981"
            text = f"{ms}ms"

        badge.setText(text)
        badge.setStyleSheet(f"""
            QLabel#latency_badge {{
                background-color: {bg_color};
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                border-radius: 4px;
                padding: 2px 6px;
            }}
        """)
  
#============= 頻道面板 =========================================================================
    def init_channel_panel(self):  # 初始化頻道面板
        print("🚀 [DEBUG] ChannelPanelManager 初始化中...")
        self.win.channel_panel = QWidget(self.win)
        layout = QVBoxLayout(self.win.channel_panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.win.channel_list = QListWidget()
        self.win.channel_list.setObjectName("channel_list")
        self.win.channel_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.win.channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 👈 新增：允許自訂右鍵選單
        self.win.channel_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.win.channel_list.customContextMenuRequested.connect(self.show_channel_list_context_menu)
        
        # 串接滾動觸發事件，實現滾動到底部自動載入更多頻道
        def _on_scroll_valueChanged(value):
            sb = self.win.channel_list.verticalScrollBar()
            if value >= sb.maximum() - 50:
                self.load_live_channels(reset=False)
        self.win.channel_list.verticalScrollBar().valueChanged.connect(_on_scroll_valueChanged)
        
        self.win.channel_list.verticalScrollBar().valueChanged.connect(self.win.on_channel_scroll)

        # ✅ 修正：改為綁定 ChannelPanelManager 內部的點擊處理函數
        self.win.channel_list.itemClicked.connect(self.on_channel_item_clicked)

        self.win.panel_title = QLabel("電視直播")
        self.win.panel_title.setObjectName("panel_title")
        layout.addWidget(self.win.panel_title)

        self.win.tools_container = QWidget()
        tools_layout = QHBoxLayout(self.win.tools_container)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(6)

        self.win.btn_group_menu = QPushButton("全部分組  ▼")
        self.win.btn_group_menu.clicked.connect(self.show_group_menu)
        tools_layout.addWidget(self.win.btn_group_menu, stretch=1)

        self.win.btn_sort_menu = QPushButton("預設排序  ▼")
        self.win.btn_sort_menu.clicked.connect(self.show_sort_menu)
        tools_layout.addWidget(self.win.btn_sort_menu, stretch=1)

        self.win.btn_ping_test = QPushButton("⚡ 測速")
        self.win.btn_ping_test.clicked.connect(self.toggle_ping_test)
        tools_layout.addWidget(self.win.btn_ping_test)

        channel_menu_btns = [
            self.win.btn_group_menu,
            self.win.btn_sort_menu,
            self.win.btn_ping_test,
        ]
        
        for btn in channel_menu_btns:
            btn.setStyleSheet("")
            btn.setProperty("role", "menu_btn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        layout.addWidget(self.win.tools_container)

        self.win.search_box = QLineEdit()
        self.win.search_box.setPlaceholderText("搜尋頻道...")
        self.win.search_box.textChanged.connect(self.filter_channels)
        layout.addWidget(self.win.search_box)

        self.win.filter_container = QWidget()
        filter_layout = QHBoxLayout(self.win.filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filters = ["全部", "4K", "FHD", "HD"]

        if not hasattr(self.win, 'filter_btn_list'):
            self.win.filter_btn_list = []

        for i, text in enumerate(filters):
            btn = QPushButton(text)
            is_active = (i == 0)
            btn.setProperty("role", "filter_btn")
            btn.setProperty("active", "true" if is_active else "false")
            btn.clicked.connect(lambda checked, t=text, b=btn: self.set_quality_filter(t, b))
            self.win.filter_btn_list.append(btn)
            filter_layout.addWidget(btn)

        layout.addWidget(self.win.filter_container)

        self.win.loading_bar = QProgressBar()
        self.win.loading_bar.setRange(0, 100)
        self.win.loading_bar.setValue(0)
        self.win.loading_bar.setFixedHeight(20)
        self.win.loading_bar.setTextVisible(True)
        self.win.loading_bar.setFormat("%v / %m (%p%)")
        self.win.loading_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.win.loading_bar.setVisible(False)
        layout.addWidget(self.win.loading_bar)

        layout.addWidget(self.win.channel_list, stretch=1)

        self.win.channel_panel.setMinimumWidth(440)  # 加寬整體頻道面板，提供舒適的寬度
        self.win.channel_panel.setMaximumWidth(1100)
        self.win.main_splitter.addWidget(self.win.channel_panel)

        self.load_live_channels(reset=True)

        return self.win.channel_panel
        
#=============================================================================================

    def set_quality_filter(self, quality, clicked_btn):
        self.win.current_quality = quality
        for btn in self.win.filter_btn_list:
            is_target = (btn == clicked_btn)
            btn.setProperty("active", "true" if is_target else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.load_live_channels(reset=True)
        
#=============================================================================================
    
    def on_channel_item_clicked(self, item):
        if not item:
            return

        url = item.data(Qt.ItemDataRole.UserRole) or ""
        ch = item.data(Qt.ItemDataRole.UserRole + 1) or {}
        name = ch.get('name', '') if isinstance(ch, dict) else item.text()
        clean_name = name.strip()

        # ✅ 點擊時強制寫入全域頻道名稱，並印出 Log
        self.win.current_channel_name = clean_name
        print(f"📌 [DEBUG] 頻道已點擊，寫入 current_channel_name: '{clean_name}'")

        idx = self.win.active_player_index
        if 0 <= idx < len(self.win.video_widgets):
            w = self.win.video_widgets[idx]
            w.channel_info = {'name': clean_name, 'url': url}
            w.channel_url = url
            w.channel_name = clean_name
            w.has_media = True

        self.win.play_channel(item)
        
        self.win.screen_mgr.update_screen_borders()

        # 🎯 直接調用唯一正確的方法 (已確認 epg_panel.py 只有此方法)
        if self.win.epg_panel:
            self.win.epg_panel.update_epg_content(clean_name)
                
#=============================================================================================
        
    def _get_current_epg_title(self, ch):
        """🟢 智能版：優先讀內存字典，內存無先讀SQLite，並有快取防止卡頓"""
        epg_cache = getattr(self.win, 'epg_data', {}) or getattr(self.win, 'epg_cache', {}) or {}
        
        tvg_id = ""
        name = ""
        keys_to_check = []
        if isinstance(ch, dict):
            tvg_id = ch.get('tvg_id', '')
            name = ch.get('name', '')
            if tvg_id:
                keys_to_check.append(str(tvg_id).lower().strip())
                keys_to_check.append(_clean_epg_key(tvg_id))
            if ch.get('tvg_name'):
                keys_to_check.append(_clean_epg_key(ch.get('tvg_name')))
            if name:
                raw_name = str(name).strip()
                keys_to_check.append(raw_name.lower())
                keys_to_check.append(_clean_epg_key(raw_name))

        # 🎯 建立快取字典，避免每次滾動都去查硬碟（呢個係唔卡嘅核心）
        if not hasattr(self, '_epg_title_cache'):
            self._epg_title_cache = {}
        cache_key = f"{tvg_id}|{name}"
        if cache_key in self._epg_title_cache:
            return self._epg_title_cache[cache_key]

        title = ""
        # 1. 優先查內存字典（速度最快）
        for k in keys_to_check:
            if k and k in epg_cache:
                for p in epg_cache[k]:
                    try:
                        s_raw = p.get('start', '').split()[0][:14]
                        e_raw = p.get('stop', '').split()[0][:14]
                        if len(s_raw) >= 12:
                            st = datetime.strptime(s_raw.ljust(14, '0'), "%Y%m%d%H%M%S")
                            et = datetime.strptime(e_raw.ljust(14, '0'), "%Y%m%d%H%M%S")
                            now = datetime.now()
                            if st <= now <= et:
                                title = p.get('title', '')
                                break
                    except Exception:
                        continue
                if title:
                    break

        # 2. 內存無，回退查 SQLite 資料庫（只會查一次，之後有快取）
        if not title and hasattr(self.win, 'epg_db') and self.win.epg_db:
            try:
                title = self.win.epg_db.get_current_program(tvg_id, name)
            except Exception:
                pass

        # 記入快取
        self._epg_title_cache[cache_key] = title
        return title
        
#=============================================================================================
   
    def _get_channel_row_widget(self, ch, i, is_fav):
        """🎯 重構：帶有完美 R 角台徽、SVG Icon、無黑邊與青色 EPG 的頻道卡片"""
        item_widget = QWidget()
        
        iw_layout = QHBoxLayout(item_widget)
        iw_layout.setContentsMargins(0, 0, 0, 0)
        iw_layout.setSpacing(10)

        # ----------------------------------------------------
        # 1. Logo Box (設為透明背景，徹底隱藏灰黑色輪廓)
        # ----------------------------------------------------
        logo_box = QLabel()
        logo_box.setFixedSize(36, 26)
        logo_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_box.setStyleSheet("background: transparent; border: none;")
        logo_box.setText("")

        import urllib.parse
        # 1. 多重相容 M3U 的台徽欄位 (logo / tvg-logo / tvg_logo)
        logo_url = (ch.get('logo') or ch.get('tvg-logo') or ch.get('tvg_logo') or '') if isinstance(ch, dict) else ''
        
        # 2. 若無直接台徽，優先讀取乾淨的 tvg-name；若無則自動過濾 4K/字幕/括號等雜訊
        if not logo_url and isinstance(ch, dict):
            raw_name = ch.get('tvg-name') or ch.get('tvg_name') or ch.get('name', '')
            clean_name = re.sub(r'(?i)(4k|fhd|hd|sd|hevc|60fps|\[.*?\]|\(.*?\))', '', raw_name).strip()
            
            if clean_name:
                logo_templates = self.win.current_logo_template or "https://live.fanmingming.cn/tv/{name}.png"
                for tpl in logo_templates.split(','):
                    tpl = tpl.strip()
                    if '{name}' in tpl:
                        logo_url = tpl.replace('{name}', clean_name)
                        break

        pixmap_loaded = False

        if logo_url and logo_url.startswith('http'):
            if not os.path.exists('logo_cache'):
                os.makedirs('logo_cache', exist_ok=True)
            logo_hash = hashlib.md5(logo_url.encode('utf-8')).hexdigest()
            logo_path = os.path.join('logo_cache', f"{logo_hash}.png")
            
            if os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    # 🎯 保持長寬比不變形 + 圓角裁切 (R角)
                    rounded_pix = get_rounded_pixmap(pixmap, QSize(36, 26), radius=5)
                    logo_box.setPixmap(rounded_pix)
                    pixmap_loaded = True
            else:
                # 🎯 防重鎖：避免快速滾動時，同時啟動幾百個Logo線程引發卡頓
                if not hasattr(self, '_logo_download_set'):
                    self._logo_download_set = set()
                if logo_url not in self._logo_download_set:
                    self._logo_download_set.add(logo_url)
                    if not hasattr(self, '_logo_threads'):
                        self._logo_threads = []
                        
                    worker = LogoFetchThread(logo_url, logo_path, logo_box)
                    
                    def _on_logo_done(p, b):
                        try:
                            pix = QPixmap(p)
                            if not pix.isNull():
                                b.setPixmap(get_rounded_pixmap(pix, QSize(36, 26), radius=5))
                        except RuntimeError:
                            pass
                        finally:
                            self._logo_download_set.discard(logo_url)

                    worker.finished_signal.connect(_on_logo_done)
                    self._logo_threads.append(worker)
                    worker.start()

        # 🎯 當台徽無法加載或未找到時：Fallback 使用 TV SVG 圖示，背景保持隱形
        if not pixmap_loaded:
            if IconManager:
                try:
                    tv_icon = IconManager.get_icon("tv", color="#8a8aa0", size=30)
                    logo_box.setPixmap(tv_icon.pixmap(36, 26))
                except Exception:
                    logo_box.setText("")
            else:
                logo_box.setText("")

        iw_layout.addWidget(logo_box)

        # ----------------------------------------------------
        # 2. 文字垂直佈局容器 (頻道名稱 + 青色 EPG 節目)
        # ----------------------------------------------------
        text_layout = QVBoxLayout()
        text_layout.setSpacing(10)
        text_layout.setContentsMargins(0, 0, 0, 0)

        name = ch.get('name', '未知頻道') if isinstance(ch, dict) else str(ch)
        group = ch.get('group', '') if isinstance(ch, dict) else ''

        clean_name = re.sub(r'[^\w\s\u4e00-\u9fff]', '', name).strip() #修改方案 2：萬能防護（用 Regex 自動清走所有 Emoji，避免硬編碼）
        lbl_text = f"{i + 1:03d}   {clean_name}"  # 三位數補零 (001, 002, 003)

        if group and group not in ['未分類', 'Undefined']:
            lbl_text += f"   [{group}]"
        
        lbl_name = QLabel(lbl_text)
        lbl_name.setProperty("role", "channel_label")
        text_layout.addWidget(lbl_name)

        # ----------------------------------------------------
        # 3. 查詢當前 EPG 節目並顯示青色字體 ( Cyan #00f2fe )
        # ----------------------------------------------------
        current_prog = self._get_current_epg_title(ch) if isinstance(ch, dict) else ""
        if not current_prog and isinstance(ch, dict):
            # 相容可以直接傳入 epg 或 current_program 欄位的資料格式
            current_prog = ch.get('epg', '') or ch.get('current_program', '')

        if current_prog:
            lbl_epg = QLabel(f"▶ {current_prog}")
            lbl_epg.setStyleSheet("color: #00f2fe; font-size: 12px; font-weight: 400; background: transparent;")
            text_layout.addWidget(lbl_epg)

        iw_layout.addLayout(text_layout, stretch=1)

        # ----------------------------------------------------
        # 4. 右側收藏按鈕 (Star SVG 圖示，徹底清空 Emoji 防止重疊)
        # ----------------------------------------------------
        star_btn = QPushButton()
        star_btn.setText("")
        star_btn.setFixedSize(30, 30)
        star_btn.setProperty("role", "star_btn")
        star_btn.setProperty("favorited", "true" if is_fav else "false")
        star_btn.setCursor(Qt.CursorShape.PointingHandCursor)

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

        # 🎯 極簡修復：完全統一使用主視窗嘅圖示管理器，徹底鎖死兩個狀態
        star_btn.setText("")
        star_btn.setIcon(QIcon())
        
        if hasattr(self.win, '_set_btn_svg_icon'):
            self.win._set_btn_svg_icon(star_btn, "star_filled" if is_fav else "star_outline")

        star_btn.clicked.connect(lambda checked=False, target_ch=ch, btn=star_btn: self.win.on_star_clicked(target_ch, btn))

        iw_layout.addWidget(star_btn)
        return item_widget
        
#=============================================================================================
    
    def load_live_channels(self, reset=True):
        
        # 根據「播放網址 (url)」精準去重，確保保留相同名稱但不同線路的頻道
        if hasattr(self, 'channels') and isinstance(self.channels, list):
            self.channels = list({ch.get('url'): ch for ch in self.channels if isinstance(ch, dict) and ch.get('url')}.values())
            
        if self.win.channel_list_mode != 'live':
            return

        # 1. 取得頻道資料（多重路徑相容，確保拿得到數據）
        # 新代碼 (直接攞，因為我哋已經保證佢存在)
        all_data = self.win.all_channels_data or self.win.channels

        # 2. 當 reset=True 或快取尚未建立時，重新過濾與整理頻道
        if reset or not hasattr(self.win, 'filtered_channels_cache') or not self.win.filtered_channels_cache:
            self.win.channel_list.clear()
            self.win.rendered_channel_count = 0
            self.win.filtered_channels_cache = []

            # 同步數據至主視窗屬性，避免其他元件找不到
            if all_data and not self.win.all_channels_data:
                self.win.all_channels_data = all_data

            if not self.win.m3u_sources and not all_data:
                item = QListWidgetItem("⚠️ 未有任何訂閱源，請打開文件夾添加 M3U 網址")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setSizeHint(QSize(0, 62))
                self.win.channel_list.addItem(item)
                return

            search_keyword = self.win.search_box.text().strip().lower() if self.win.search_box.text() else ""
            quality_filter = self.win.current_quality
            group_filter = self.win.current_group_filter

            if not all_data and not search_keyword:
            # 🎯 優先讀取主視窗權威標誌 is_m3u_loading，徹底消除微秒級狀態不一致
                is_fetching = self.win.is_m3u_loading
                
                if not is_fetching:
                    # 備用：檢查背景線程
                    for worker_attr in ['m3u_worker', 'fetch_worker', 'm3u_fetch_worker']:
                        worker = getattr(self.win, worker_attr, None) or getattr(self, worker_attr, None)  # worker = getattr(self.win, worker_attr, None) —— 因為 worker_attr 係變數（會變成 m3u_worker 或者 fetch_worker），唔可以用點（.）直接訪問。
                        if worker and hasattr(worker, 'isRunning') and worker.isRunning():
                            is_fetching = True
                            break

                loading_bar = self.win.loading_bar
                # 🎯 即使 is_m3u_loading 為 False，只要有訂閱源，啟動時仍顯示「加載中」而非「加載失敗」
                if is_fetching or self.win.m3u_sources:
                    msg = "⏳ 正在加載 M3U 頻道清單，請稍候..."
                else:
                    msg = "❌ 加載失敗，請重啟播放器或檢查網絡"

                item = QListWidgetItem(msg)
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setSizeHint(QSize(0, 65))
                self.win.channel_list.addItem(item)
                return

            for ch in all_data:
                name = ch.get('name', '') if isinstance(ch, dict) else str(ch)
                group = ch.get('group', '未分類') or '未分類' if isinstance(ch, dict) else '未分類'

                if group_filter != "全部分組" and group != group_filter:
                    continue

                if search_keyword and (search_keyword not in name.lower() and search_keyword not in group.lower()):
                    continue

                if quality_filter != "全部" and quality_filter.lower() not in name.lower():
                    continue

                self.win.filtered_channels_cache.append(ch)

            sort_mode = self.win.current_sort_mode
            if sort_mode == "name_asc":
                self.win.filtered_channels_cache.sort(key=lambda x: x.get('name', '').lower() if isinstance(x, dict) else str(x))
            elif sort_mode == "name_desc":
                self.win.filtered_channels_cache.sort(key=lambda x: x.get('name', '').lower() if isinstance(x, dict) else str(x), reverse=True)
            elif sort_mode == "latency_asc":
                latencies = self.win.channel_latencies
                def _get_sort_key(ch):
                    url = ch.get('url', '') if isinstance(ch, dict) else ''
                    ms = latencies.get(url, 999999)
                    return ms if ms > 0 else 999999
                self.win.filtered_channels_cache.sort(key=_get_sort_key)

        # 3. 分頁增量繪製 UI 列表
        fav_list = self.win.favorites_list
        fav_urls = {f['url'] for f in fav_list if isinstance(f, dict) and 'url' in f}
        batch_size = 30
        start_idx = self.win.rendered_channel_count
        end_idx = min(start_idx + batch_size, len(self.win.filtered_channels_cache))

        if start_idx >= len(self.win.filtered_channels_cache):
            return

        self.win.channel_list.setUpdatesEnabled(False)
        for i in range(start_idx, end_idx):
            ch = self.win.filtered_channels_cache[i]
            url = ch.get('url', '') if isinstance(ch, dict) else ''
            is_fav = url in fav_urls

            item_widget = self._get_channel_row_widget(ch, i, is_fav)

            latencies = self.win.channel_latencies
            if url in latencies:
                self.update_latency_badge(item_widget, latencies[url])

            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 65))
            item.setData(Qt.ItemDataRole.UserRole, url)
            item.setData(Qt.ItemDataRole.UserRole + 1, ch)
            
            # ✅ 修正：直接將卡片的點擊事件綁定至點擊處理函數
            item_widget.mousePressEvent = lambda event, itm=item: self.on_channel_item_clicked(itm)
            
            self.win.channel_list.addItem(item)
            self.win.channel_list.setItemWidget(item, item_widget)

        self.win.rendered_channel_count = end_idx
        self.win.channel_list.setUpdatesEnabled(True)

#=============================================================================================

    def filter_channels(self):
        self.load_live_channels(reset=True)
        
#=============================================================================================

    def switch_channel_view(self, mode, clicked_btn=None):
        if clicked_btn and hasattr(self.win, 'update_sidebar_btn_styles'):
            self.win.update_sidebar_btn_styles(clicked_btn)

        self.win.channel_list_mode = mode
        self.win.channel_list.clear()

        if mode == "live":
            self.win.panel_title.setText("電視直播")
            self.win.search_box.setVisible(True)
            self.win.filter_container.setVisible(True)
            self.load_live_channels(reset=True)

        elif mode == "fav":
            self.win.panel_title.setText("我的收藏")
            self.win.search_box.setVisible(False)
            self.win.filter_container.setVisible(False)
            fav_list = self.win.favorites_list
            if not fav_list:
                item = QListWidgetItem("暫無收藏頻道")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.win.channel_list.addItem(item)
            else:
                for idx, ch in enumerate(fav_list):
                    item_widget = self._get_channel_row_widget(ch, idx, True)
                    item = QListWidgetItem()
                    item.setSizeHint(QSize(0, 65))
                    item.setData(Qt.ItemDataRole.UserRole, ch['url'])
                    item.setData(Qt.ItemDataRole.UserRole + 1, ch)
                    
                    # ✅ 修正：綁定收藏項目的點擊事件
                    item_widget.mousePressEvent = lambda event, itm=item: self.on_channel_item_clicked(itm)
                    
                    self.win.channel_list.addItem(item)
                    self.win.channel_list.setItemWidget(item, item_widget)

        elif mode in ["history", "local"]:
            is_history = (mode == "history")
            title = "最近播放" if is_history else "本地媒體"
            data_list_name = 'history_sources' if is_history else 'local_media_list'
            
            self.win.panel_title.setText(title)
            self.win.search_box.setVisible(False)
            self.win.filter_container.setVisible(True)

            # 🎯 極簡核心：直接攞原始數據，並強制「只睇前20條」（完美復刻v28速度）
            raw_list = getattr(self.win, data_list_name, [])
            display_list = raw_list[:20]
            
            fav_list = self.win.favorites_list
            all_data = self.win.all_channels_data or self.win.channels

            # 🎯 只對呢20條排序（絕對唔會卡）
            sort_mode = self.win.current_sort_mode
            if sort_mode == 'name_asc':
                display_list = sorted(display_list, key=lambda x: natural_sort_key(x.get('name', '') if isinstance(x, dict) else str(x)))
            elif sort_mode == 'name_desc':
                display_list = sorted(display_list, key=lambda x: natural_sort_key(x.get('name', '') if isinstance(x, dict) else str(x)), reverse=True)

            for idx, ch in enumerate(display_list):
                url = ch.get('url', '') if isinstance(ch, dict) else str(ch)
                fav_match = next((f for f in fav_list if isinstance(f, dict) and f.get('url') == url), {})
                all_match = next((c for c in all_data if isinstance(c, dict) and c.get('url') == url), {})

                merged_ch = all_match if all_match else (fav_match if fav_match else (ch if isinstance(ch, dict) else {'name': str(ch), 'url': url}))
                item_widget = self._get_channel_row_widget(merged_ch, idx, url in {f['url'] for f in fav_list if isinstance(f, dict)})

                layout = item_widget.layout()
                if layout.count() > 2:
                    old_btn = layout.itemAt(layout.count() - 1).widget()
                    if old_btn:
                        old_btn.deleteLater()
                    del_btn = QPushButton("❌")
                    del_btn.setFixedSize(30, 30)
                    del_btn.setProperty("role", "del_btn")
                    del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    layout.addWidget(del_btn)

                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 65))
                item.setData(Qt.ItemDataRole.UserRole, url)
                item.setData(Qt.ItemDataRole.UserRole + 1, merged_ch)

                item_widget.mousePressEvent = lambda event, itm=item: self.on_channel_item_clicked(itm)

                self.win.channel_list.addItem(item)
                self.win.channel_list.setItemWidget(item, item_widget)
                if layout.count() > 2:
                    del_btn = layout.itemAt(layout.count() - 1).widget()
                    if del_btn:
                        del_btn.clicked.connect(lambda checked=False, target_ch=ch, item_ref=item, m=mode: self.remove_history_or_local_item(target_ch, item_ref, m))

#=============================================================================================

    def remove_history_or_local_item(self, ch, item, mode):
        """移除單筆紀錄 ( history / local )"""
        attr_name = 'history_sources' if mode == 'history' else 'local_media_list'
        target_list = getattr(self.win, attr_name, [])
        if ch in target_list:
            target_list.remove(ch)
        row = self.win.channel_list.row(item)
        if row >= 0:
            self.win.channel_list.takeItem(row)
        if mode == 'history':
            self.win.save_history()

#=============================================================================================

    def show_channel_list_context_menu(self, pos):
        """右鍵菜單：一鍵清空"""
        mode = self.win.channel_list_mode
        if mode not in ["history", "local"]:
            return

        menu = RoundedMenu(self.win)
        clear_label = "🗑️ 一鍵清空最近播放" if mode == "history" else "🗑️ 一鍵清空本地媒體"
        action = QAction(clear_label, self.win)
        action.triggered.connect(lambda: self.clear_playlist(mode))
        menu.addAction(action)
        menu.exec(self.win.channel_list.mapToGlobal(pos))

#=============================================================================================

    def clear_playlist(self, mode):
        """執行清空」"""
        attr_name = 'history_sources' if mode == 'history' else 'local_media_list'
        setattr(self.win, attr_name, [])
        if mode == 'history':
            self.win.save_history()
        self.switch_channel_view(mode)

#=============================================================================================

    def add_local_media_record(self, name_or_item, url: str = None):
        """加入本地媒體紀錄 (全相容模式：支援單檔路徑、字典、列表)"""
        import os
        if not hasattr(self.win, 'local_media_list') or self.win.local_media_list is None:
            self.win.local_media_list = []

        new_items = []
        # 🎯 情況 1：傳入的是 list (批次檔案)
        if isinstance(name_or_item, list):
            for item in name_or_item:
                if isinstance(item, dict):
                    new_items.append(item)
                elif isinstance(item, str):
                    new_items.append({'name': os.path.basename(item), 'url': item})
        # 🎯 情況 2：傳入的是 dict (頻道物件)
        elif isinstance(name_or_item, dict):
            new_items.append(name_or_item)
        # 🎯 情況 3：傳入的是字串 (檔名或完整路徑)
        elif isinstance(name_or_item, str):
            item_url = url if url else name_or_item
            item_name = name_or_item if url else os.path.basename(name_or_item)
            new_items.append({'name': item_name, 'url': item_url})

        if not new_items:
            return

        # 🎯 去重：過濾掉重複的 URL
        new_urls = {x.get('url') for x in new_items if isinstance(x, dict)}
        filtered_old = [
            x for x in self.win.local_media_list 
            if isinstance(x, dict) and x.get('url') not in new_urls
        ]

        # 🎯 拼接並更新列表
        self.win.local_media_list = new_items + filtered_old

        # 🎯 尋找 sidebar 的 "local" 按鈕並觸發切換
        target_btn = None
        if hasattr(self.win, 'sidebar_btns'):
            for btn in self.win.sidebar_btns:
                if btn.toolTip() == "本地媒體":
                    target_btn = btn
                    break

        self.switch_channel_view("local", target_btn)
            
#=============================================================================================

    def load_epg_data(self, epg_urls_str):
        print(f"📡 [DEBUG] 收到 EPG 載入請求，原始網址字串: '{epg_urls_str}'")

        if not epg_urls_str or not epg_urls_str.strip():
            print("⚠️ [DEBUG] EPG 網址為空，取消線程啟動！請至『系統設置』輸入 EPG 網址")
            return
            
        os.makedirs("epg_cache", exist_ok=True)
        db_path = os.path.join("epg_cache", "epg_cache.db")
        try:
            db_conn = sqlite3.connect(db_path)
            db_cursor = db_conn.cursor()
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS epg_programs (
                    ch_key TEXT,
                    start TEXT,
                    stop TEXT,
                    title TEXT
                )
            ''')
            db_conn.commit()
            db_conn.close()
        except Exception as e:
            print(f"❌ 初始化 EPG 資料庫失敗: {e}")

        urls = [u.strip() for u in epg_urls_str.split(',') if u.strip()]
        print(f"🔍 [DEBUG] 解析出 {len(urls)} 個有效 EPG 網址: {urls}")

        try:
            if hasattr(self, 'epg_worker') and self.epg_worker:
                if self.epg_worker.isRunning():
                    self.epg_worker.quit()
                    self.epg_worker.wait(1000)
        except RuntimeError:
            self.epg_worker = None

                # 直接呼叫主視窗的 EPG 下載函數（使用 epg_manager 的 SQLite 流）
        if hasattr(self.win, 'load_epg') and urls:
            self.win.load_epg(urls[0])
