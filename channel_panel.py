# [代碼起點] ...
from config import *  # 匯入配置
from config import _script_dir  # 專案/exe 目錄
from datetime import datetime  # 匯入時間
from skin import IconManager  # 圖示管理
from widgets import RoundedMenu  # 圓角選單

#=============================================================================================
# 全局輔助函數
#=============================================================================================

class SearchFocusFilter(QObject):  # 搜尋框焦點過濾
    """點擊搜尋框外部時移除焦點，避免整個視窗的快捷鍵被輸入框吃掉。"""
    def __init__(self, search_box):  # 初始化
        super().__init__(search_box)  # 父物件
        self.search_box = search_box  # 搜尋框

    def eventFilter(self, watched, event):  # 事件過濾
        if event.type() == QEvent.Type.MouseButtonPress and self.search_box.hasFocus():  # 點擊時
            try:  # 取得點擊的全域座標
                target = QApplication.widgetAt(event.globalPosition().toPoint())  # 點到的控件
            except AttributeError:  # 舊式事件
                return False  # 不處理
            if target is None or (target is not self.search_box and not self.search_box.isAncestorOf(target)):  # 點到外部
                self.search_box.clearFocus()  # 退出搜尋框
        return False  # 不攔截事件

# 自然排序鍵
def natural_sort_key(s):
    """自然排序鍵"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]  # 拆解數字排序

# 圓角縮放圖
def get_rounded_pixmap(pixmap: QPixmap, target_size: QSize, radius: int = 5) -> QPixmap:
    """圓角裁切"""
    if pixmap.isNull():  # 圖片為空
        return pixmap  # 原樣返回

    scaled_pixmap = pixmap.scaled(  # 比例縮放
        target_size, 
        Qt.AspectRatioMode.KeepAspectRatio, 
        Qt.TransformationMode.SmoothTransformation
    )

    out_pixmap = QPixmap(scaled_pixmap.size())  # 建立畫布
    out_pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景

    painter = QPainter(out_pixmap)  # 建立畫筆
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)  # 抗鋸齒
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)  # 平滑變換

    path = QPainterPath()  # 繪圖路徑
    path.addRoundedRect(0.0, 0.0, float(scaled_pixmap.width()), float(scaled_pixmap.height()), float(radius), float(radius))  # 加圓角矩形
    painter.setClipPath(path)  # 路徑裁切
    painter.drawPixmap(0, 0, scaled_pixmap)  # 繪製圖片
    painter.end()  # 結束繪製

    return out_pixmap  # 返回結果

# 清理EPG鍵名
def _clean_epg_key(text):
    """清理頻道名稱"""
    if not text:  # 文字為空
        return ""  # 回傳空字串
    text = str(text).lower()  # 轉為小寫
    text = re.sub(r'(4k|fhd|hd|sd|hevc|60fps|頻道|台)', '', text)  # 濾除畫質詞
    text = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text)  # 濾除特殊符
    return text.strip()  # 去頭尾空格

# 非同步下載台標
class LogoFetchThread(QThread):
    """台標下載線程"""
    finished_signal = pyqtSignal(str, object)  # 下載完成訊號

    def __init__(self, url, path, box):
        super().__init__()  # 基類初始化
        self.url = url  # 儲存網址
        self.path = path  # 儲存路徑
        self.box = box  # 儲存組件

    def run(self):
        try:
            import urllib.parse, urllib.request  # 匯入網路庫
            safe_url = urllib.parse.quote(self.url, safe=':/?&=#%')  # 轉碼網址
            req = urllib.request.Request(safe_url, headers={'User-Agent': 'Mozilla/5.0'})  # 建立請求
            with urllib.request.urlopen(req, timeout=4) as resp:  # 發送請求
                data = resp.read()  # 讀取數據
                with open(self.path, "wb") as f:  # 開啟檔案
                    f.write(data)  # 寫入檔案
                self.finished_signal.emit(self.path, self.box)  # 發射訊號
        except Exception:
            pass  # 忽略異常

#=============================================================================================
# 頻道面板管理器類
#=============================================================================================

class ChannelPanelManager:  # 面板管理器
    # ----- 初始化 -----
    def __init__(self, main_window):  # 建構函數
        self.win = main_window  # 綁定主視窗
        self._logo_download_set = set()  # 下載集合
        self._logo_threads = []  # 線程列表
        self.is_pinging = False  # 測速狀態
        self.ping_worker = None  # 測速線程

    # ----- 側邊欄 -----
    def init_sidebar(self):
        self.win.sidebar = QWidget()  # 建立側邊欄
        self.win.sidebar.setObjectName("sidebar")  # 設置名稱
        self.win.sidebar.setFixedWidth(60)  # 固定寬度

        layout = QVBoxLayout(self.win.sidebar)  # 垂直佈局
        layout.setContentsMargins(0, 10, 0, 10)  # 設置邊距
        layout.setSpacing(8)  # 組件間距

        logo = QPushButton("K20")  # Logo按鈕
        logo.setObjectName("sidebar_logo")  # 設定名稱
        layout.addWidget(logo)  # 加入佈局

        self.win.sidebar_btns = []  # 按鈕清單
        
        view_buttons = [  # 視圖按鈕組
            ("tv", "直播頻道", "live"),
            ("star", "我的收藏", "fav"),
            ("folder", "最近播放", "history"),
            ("film", "本地媒體", "local")
        ]
        
        for icon_name, tip, mode in view_buttons:
            btn = QPushButton("")  # 視圖按鈕
            btn.setToolTip(tip)  # 提示文字
            btn.setProperty("icon_name", icon_name)  # 圖示屬性
            btn.setIconSize(QSize(50, 50))  # 圖示尺寸
            btn.clicked.connect(lambda checked, b=btn, m=mode: self.switch_channel_view(m, b, True))  # 切換事件（清搜尋）
            self.win.sidebar_btns.append(btn)  # 存入列表
            layout.addWidget(btn)  # 加入佈局
            
        action_buttons = [  # 功能按鈕組
            ("m3u", "訂閱列表管理", self.win.shortcut_mgr.open_m3u_manager),
            ("help", "快捷說明", self.win.shortcut_mgr.open_help_dialog)
        ]
        
        for icon_name, tip, slot in action_buttons:
            btn = QPushButton("")  # 功能按鈕
            btn.setToolTip(tip)  # 提示文字
            btn.setProperty("icon_name", icon_name)  # 圖示屬性
            btn.setIconSize(QSize(50, 50))  # 圖示尺寸
            btn.clicked.connect(slot)  # 觸發事件
            self.win.sidebar_btns.append(btn)  # 存入列表
            layout.addWidget(btn)  # 加入佈局

        layout.addStretch()  # 彈性伸縮
        
        setting_btn = QPushButton("")  # 設定按鈕
        setting_btn.setToolTip("系統設置")  # 提示文字
        setting_btn.setObjectName("setting_btn")  # 設置名稱
        setting_btn.setProperty("icon_name", "gear")  # 圖示屬性
        setting_btn.setIconSize(QSize(50, 50))  # 圖示尺寸
        setting_btn.clicked.connect(self.win.shortcut_mgr.open_settings_dialog)  # 打開設定
        self.win.sidebar_btns.append(setting_btn)  # 存入列表
        layout.addWidget(setting_btn)  # 加入佈局
        
        if self.win.sidebar_btns:  # 按鈕非空
            self.win.update_sidebar_btn_styles(self.win.sidebar_btns[0])  # 高亮首鈕
            
        self.win.main_layout.addWidget(self.win.sidebar)  # 嵌入主佈局

    # ----- 頻道面板初始化 -----
    def init_channel_panel(self):  # 建立頻道面板
        print("🚀 [DEBUG] ChannelPanelManager 初始化中...")  # 調試輸出
        self.win.channel_panel = QWidget(self.win)  # 面板容器
        layout = QVBoxLayout(self.win.channel_panel)  # 垂直佈局
        layout.setContentsMargins(20, 20, 20, 20)  # 外邊距
        layout.setSpacing(12)  # 組件間隔

        self.win.channel_list = QListWidget()  # 頻道列表
        self.win.channel_list.setObjectName("channel_list")  # 設置名稱
        self.win.channel_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 禁用焦點框
        self.win.channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 自動滾動條
        
        self.win.channel_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # 右鍵選單模式
        self.win.channel_list.customContextMenuRequested.connect(self.show_channel_list_context_menu)  # 綁定右鍵
        
        def _on_scroll_valueChanged(value):
            sb = self.win.channel_list.verticalScrollBar()  # 取得滾動條
            if value >= sb.maximum() - 50:  # 觸底檢測
                self.load_live_channels(reset=False)  # 載入更多
        self.win.channel_list.verticalScrollBar().valueChanged.connect(_on_scroll_valueChanged)  # 綁定滾動
        
        self.win.channel_list.verticalScrollBar().valueChanged.connect(self.win.on_channel_scroll)  # 懶加載監聽

        self.win.channel_list.itemClicked.connect(self.on_channel_item_clicked)  # 綁定點擊

        self.win.panel_title = QLabel("電視直播")  # 面板標題
        self.win.panel_title.setObjectName("panel_title")  # 標題名稱
        layout.addWidget(self.win.panel_title)  # 加入佈局

        self.win.tools_container = QWidget()  # 工具欄容器
        tools_layout = QHBoxLayout(self.win.tools_container)  # 水平佈局
        tools_layout.setContentsMargins(0, 0, 0, 0)  # 清除邊距
        tools_layout.setSpacing(6)  # 工具間距

        self.win.btn_group_menu = QPushButton("全部分組")  # 分組按鈕
        self.win.btn_group_menu.clicked.connect(self.show_group_menu)  # 綁定選單
        tools_layout.addWidget(self.win.btn_group_menu, stretch=1)  # 加入工具欄

        self.win.btn_sort_menu = QPushButton("預設排序")  # 排序按鈕
        self.win.btn_sort_menu.clicked.connect(self.show_sort_menu)  # 綁定選單
        tools_layout.addWidget(self.win.btn_sort_menu, stretch=1)  # 加入工具欄

        self.win.btn_ping_test = QPushButton("測速⚡")  # 測速按鈕
        self.win.btn_ping_test.clicked.connect(self.toggle_ping_test)  # 綁定測速
        tools_layout.addWidget(self.win.btn_ping_test)  # 加入工具欄

        channel_menu_btns = [  # 工具按鈕組
            self.win.btn_group_menu,
            self.win.btn_sort_menu,
            self.win.btn_ping_test,
        ]
        
        for btn in channel_menu_btns:
            btn.setStyleSheet("")  # 清空樣式
            btn.setProperty("role", "menu_btn")  # 設定角色
            btn.style().unpolish(btn)  # 刷新前
            btn.style().polish(btn)  # 刷新後

        layout.addWidget(self.win.tools_container)  # 加入佈局

        self.win.search_box = QLineEdit()  # 搜尋輸入框
        self.win.search_box.setPlaceholderText("搜尋頻道...")  # 提示文字
        self.win.search_box.setClearButtonEnabled(True)  # 顯示清除按鈕
        self.win.search_box.textChanged.connect(self.filter_channels)  # 內容改變
        layout.addWidget(self.win.search_box)  # 加入佈局

        self._search_focus_filter = SearchFocusFilter(self.win.search_box)  # 點擊外部退出搜尋
        QApplication.instance().installEventFilter(self._search_focus_filter)  # 全域安裝

        self.win.filter_container = QWidget()  # 畫質過濾器
        filter_layout = QHBoxLayout(self.win.filter_container)  # 水平佈局
        filter_layout.setContentsMargins(0, 0, 0, 0)  # 清除邊距
        filters = ["全部", "4K", "FHD", "HD"]  # 畫質標籤

        for i, text in enumerate(filters):
            btn = QPushButton(text)  # 過濾按鈕
            is_active = (i == 0)  # 預設選中
            btn.setProperty("role", "filter_btn")  # 設定角色
            btn.setProperty("active", "true" if is_active else "false")  # 選中屬性
            btn.clicked.connect(lambda checked, t=text, b=btn: self.set_quality_filter(t, b))  # 點擊過濾
            self.win.filter_btn_list.append(btn)  # 存入列表
            filter_layout.addWidget(btn)  # 加入佈局

        layout.addWidget(self.win.filter_container)  # 加入佈局

        self.win.loading_bar = QProgressBar()  # 進度條
        self.win.loading_bar.setRange(0, 100)  # 範圍設置
        self.win.loading_bar.setValue(0)  # 初始值
        self.win.loading_bar.setFixedHeight(20)  # 固定高度
        self.win.loading_bar.setTextVisible(True)  # 顯示文字
        self.win.loading_bar.setFormat("%v / %m (%p%)")  # 格式化
        self.win.loading_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 文字置中

        self.win.loading_bar.setVisible(False)  # 預設隱藏
        layout.addWidget(self.win.loading_bar)  # 加入佈局

        layout.addWidget(self.win.channel_list, stretch=1)  # 列表伸展

        self.win.channel_panel.setMinimumWidth(450)  # 最小寬度
        self.win.channel_panel.setMaximumWidth(1000)  # 最大寬度
        self.win.main_splitter.addWidget(self.win.channel_panel)  # 放入分割器

        self.load_live_channels(reset=True)  # 載入直播

        return self.win.channel_panel  # 返回面板

    # ----- 視圖切換 -----
    def switch_channel_view(self, mode, clicked_btn=None, clear_search=False):
        if clicked_btn:  # 點擊按鈕存在
            self.win.update_sidebar_btn_styles(clicked_btn)  # 刷新按鈕

        if clear_search and self.win.search_box:  # 切換列表時清空搜尋
            self.win.search_box.blockSignals(True)  # 避免立即重繪
            self.win.search_box.clear()  # 清空關鍵字
            self.win.search_box.blockSignals(False)  # 恢復訊號

        self.win.channel_list_mode = mode  # 更新模式
        self.win.channel_list.clear()  # 清空列表
        self.win.search_box.setVisible(True)  # 所有視圖都能搜尋
        keyword = self.win.search_box.text().strip().lower()  # 搜尋關鍵

        if mode == "live":  # 直播視圖
            self.win.panel_title.setText("電視直播")  # 設標題
            self.win.filter_container.setVisible(True)  # 顯過濾
            self.load_live_channels(reset=True)  # 加載頻道

        elif mode == "fav":  # 收藏視圖
            self.win.panel_title.setText("我的收藏")  # 設標題
            self.win.filter_container.setVisible(False)  # 隱過濾
            fav_list = [  # 先過濾再顯示
                ch for ch in self.win.favorites_list
                if isinstance(ch, dict) and ch.get('url') and (
                    not keyword or keyword in (str(ch.get('name', '')) + ' ' + str(ch.get('url', ''))).lower()
                )
            ]  # 收藏清單
            if not fav_list:  # 無收藏
                item = QListWidgetItem("暫無收藏頻道")  # 無資料項
                item.setFlags(Qt.ItemFlag.NoItemFlags)  # 禁用點擊
                self.win.channel_list.addItem(item)  # 加入列表
            else:
                for idx, ch in enumerate(fav_list):  # 遍歷收藏
                    item_widget = self._get_channel_row_widget(ch, idx, True)  # 建立卡片
                    item = QListWidgetItem()  # 建立列表項
                    item.setSizeHint(QSize(0, 65))  # 設定尺寸
                    item.setData(Qt.ItemDataRole.UserRole, ch['url'])  # 存網址
                    item.setData(Qt.ItemDataRole.UserRole + 1, ch)  # 存物件
                    
                    item_widget.mousePressEvent = lambda event, itm=item: self.on_channel_item_clicked(itm)  # 點擊卡片
                    
                    self.win.channel_list.addItem(item)  # 加入列表
                    self.win.channel_list.setItemWidget(item, item_widget)  # 綁定卡片

        elif mode in ["history", "local"]:  # 歷史/本地
            is_history = (mode == "history")  # 是否歷史
            title = "最近播放" if is_history else "本地媒體"  # 設定標題
            data_list_name = 'history_sources' if is_history else 'local_media_list'  # 數據源名
            
            self.win.panel_title.setText(title)  # 設定標題
            self.win.filter_container.setVisible(False)  # 隱過濾（此視圖未支援畫質）

            raw_list = getattr(self.win, data_list_name, [])  # 安全取值
            raw_list = [  # 先過濾再顯示
                ch for ch in raw_list
                if isinstance(ch, dict) and (
                    not keyword or keyword in (str(ch.get('name', '')) + ' ' + str(ch.get('url', ''))).lower()
                )
            ]  # 過濾後清單
            display_list = raw_list[:20]  # 只取前20
            
            fav_list = self.win.favorites_list  # 取收藏
            all_data = self.win.all_channels_data or self.win.channels  # 取全部

            sort_mode = self.win.current_sort_mode  # 取排序
            if sort_mode == 'name_asc':  # 名稱升序
                display_list = sorted(display_list, key=lambda x: natural_sort_key(x.get('name', '') if isinstance(x, dict) else str(x)))
            elif sort_mode == 'name_desc':  # 名稱降序
                display_list = sorted(display_list, key=lambda x: natural_sort_key(x.get('name', '') if isinstance(x, dict) else str(x)), reverse=True)

            for idx, ch in enumerate(display_list):  # 遍歷顯示
                url = ch.get('url', '') if isinstance(ch, dict) else str(ch)  # 取網址
                fav_match = next((f for f in fav_list if isinstance(f, dict) and f.get('url') == url), {})  # 匹對收藏
                all_match = next((c for c in all_data if isinstance(c, dict) and c.get('url') == url), {})  # 匹對全部

                merged_ch = all_match if all_match else (fav_match if fav_match else (ch if isinstance(ch, dict) else {'name': str(ch), 'url': url}))  # 合併數據
                item_widget = self._get_channel_row_widget(merged_ch, idx, url in {f['url'] for f in fav_list if isinstance(f, dict)})  # 建立卡片

                layout = item_widget.layout()  # 取卡片佈局
                if layout.count() > 2:  # 有舊按鈕
                    old_btn = layout.itemAt(layout.count() - 1).widget()  # 取得按鈕
                    if old_btn:  # 存在按鈕
                        old_btn.deleteLater()  # 安全刪除
                    del_btn = QPushButton("✕")  # 刪除按鈕（與搜尋框同款叉號）
                    del_btn.setFixedSize(28, 28)  # 固定尺寸
                    del_btn.setProperty("role", "del_btn")  # 設置角色
                    del_btn.setCursor(Qt.CursorShape.PointingHandCursor)  # 手型鼠標
                    del_btn.setStyleSheet(
                        "QPushButton { background: transparent; border: none; color: #d7d7e0; "
                        "font-size: 14px; border-radius: 4px; padding: 0px; } "
                        "QPushButton:hover { background: rgba(255, 75, 75, 0.25); color: #ff6b6b; }"
                    )  # 樣式
                    layout.addWidget(del_btn)  # 加入佈局

                item = QListWidgetItem()  # 建立列表項
                item.setSizeHint(QSize(0, 65))  # 設定尺寸
                item.setData(Qt.ItemDataRole.UserRole, url)  # 存網址
                item.setData(Qt.ItemDataRole.UserRole + 1, merged_ch)  # 存物件

                item_widget.mousePressEvent = lambda event, itm=item: self.on_channel_item_clicked(itm)  # 點擊卡片

                self.win.channel_list.addItem(item)  # 加入列表
                self.win.channel_list.setItemWidget(item, item_widget)  # 綁定卡片
                if layout.count() > 2:  # 綁定刪除
                    del_btn = layout.itemAt(layout.count() - 1).widget()  # 取刪除鈕
                    if del_btn:  # 鈕存在
                        del_btn.clicked.connect(lambda checked=False, target_ch=ch, item_ref=item, m=mode: self.remove_history_or_local_item(target_ch, item_ref, m))  # 點擊刪除

    # ----- 載入頻道列表 -----
    def load_live_channels(self, reset=True):
        if isinstance(self.win.channels, list):  # 列表去重
            self.win.channels = list({ch.get('url'): ch for ch in self.win.channels if isinstance(ch, dict) and ch.get('url')}.values())
            
        if self.win.channel_list_mode != 'live':  # 非直播頁
            return  # 放行退出

        all_data = self.win.all_channels_data or self.win.channels  # 取得數據

        if reset or not self.win.filtered_channels_cache:  # 重置快取
            self.win.channel_list.clear()  # 清空列表
            self.win.rendered_channel_count = 0  # 歸零計數
            self.win.filtered_channels_cache = []  # 清空快取

            # 🎯 檢查當前選中的分組是否還存在於新數據中，若不存在則重置為「全部分組」
            valid_groups = {ch.get('group', '未分類') or '未分類' for ch in (all_data or []) if isinstance(ch, dict)}
            if self.win.current_group_filter != "全部分組" and self.win.current_group_filter not in valid_groups:
                self.win.current_group_filter = "全部分組"
                if hasattr(self.win, 'btn_group_menu'):
                    self.win.btn_group_menu.setText("全部分組 ▾")

            if all_data and not self.win.all_channels_data:  # 數據同步
                self.win.all_channels_data = all_data  # 賦值數據

            if not self.win.m3u_sources and not all_data:  # 無訂閱源
                item = QListWidgetItem("⚠️ 未有任何訂閱源，請打開文件夾添加 M3U 網址")  # 警告項目
                item.setFlags(Qt.ItemFlag.NoItemFlags)  # 禁用點擊
                item.setSizeHint(QSize(0, 62))  # 設高
                self.win.channel_list.addItem(item)  # 加入列表
                return  # 退出

            search_keyword = self.win.search_box.text().strip().lower() if self.win.search_box.text() else ""  # 取關鍵字
            quality_filter = self.win.current_quality  # 取畫質
            group_filter = self.win.current_group_filter  # 取分組

            if not all_data and not search_keyword:  # 無頻道時
                is_fetching = self.win.is_m3u_loading  # 檢查加載
                if not is_fetching:  # 未在加載
                    for worker_attr in ['m3u_worker', 'fetch_worker', 'm3u_fetch_worker']:  # 檢查線程
                        worker = getattr(self.win, worker_attr, None)  # 取線程
                        if worker and hasattr(worker, 'isRunning') and worker.isRunning():  # 線程運行
                            is_fetching = True  # 設加載中
                            break  # 中斷

                loading_bar = self.win.loading_bar  # 取進度條
                if is_fetching or self.win.m3u_sources:  # 加載提示
                    msg = "⏳ 正在加載 M3U 頻道清單，請稍候..."  # 載入中
                else:  # 失敗提示
                    msg = "❌ 加載失敗，請重啟播放器或檢查網絡"  # 失敗

                item = QListWidgetItem(msg)  # 提示項目
                item.setFlags(Qt.ItemFlag.NoItemFlags)  # 禁用點擊
                item.setSizeHint(QSize(0, 65))  # 設高
                self.win.channel_list.addItem(item)  # 加入列表
                return  # 退出

            for ch in all_data:  # 遍歷過濾
                name = ch.get('name', '') if isinstance(ch, dict) else str(ch)  # 取名稱
                group = ch.get('group', '未分類') or '未分類' if isinstance(ch, dict) else '未分類'  # 取分組

                if group_filter != "全部分組" and group != group_filter:  # 分組不符
                    continue  # 跳過

                if search_keyword and (search_keyword not in name.lower() and search_keyword not in group.lower()):  # 關鍵字不符
                    continue  # 跳過

                if quality_filter != "全部" and quality_filter.lower() not in name.lower():  # 畫質不符
                    continue  # 跳過

                self.win.filtered_channels_cache.append(ch)  # 加入快取

            sort_mode = self.win.current_sort_mode  # 取排序
            if sort_mode == "name_asc":  # 字母升序
                self.win.filtered_channels_cache.sort(key=lambda x: x.get('name', '').lower() if isinstance(x, dict) else str(x))
            elif sort_mode == "name_desc":  # 字母降序
                self.win.filtered_channels_cache.sort(key=lambda x: x.get('name', '').lower() if isinstance(x, dict) else str(x), reverse=True)
            elif sort_mode == "latency_asc":  # 延遲排序
                latencies = self.win.channel_latencies  # 取延遲字典
                def _get_sort_key(ch):  # 排序鍵
                    url = ch.get('url', '') if isinstance(ch, dict) else ''  # 取網址
                    ms = latencies.get(url, 999999)  # 取毫秒
                    return ms if ms > 0 else 999999  # 回傳權重
                self.win.filtered_channels_cache.sort(key=_get_sort_key)  # 執行排序

        fav_list = self.win.favorites_list  # 取收藏
        fav_urls = {f['url'] for f in fav_list if isinstance(f, dict) and 'url' in f}  # 收藏網址
        batch_size = 30  # 每頁數量
        start_idx = self.win.rendered_channel_count  # 開始索引
        end_idx = min(start_idx + batch_size, len(self.win.filtered_channels_cache))  # 結束索引

        if start_idx >= len(self.win.filtered_channels_cache):  # 已無數據
            return  # 直接退出

        self.win.channel_list.setUpdatesEnabled(False)  # 凍結渲染
        for i in range(start_idx, end_idx):  # 分頁繪製
            ch = self.win.filtered_channels_cache[i]  # 取得頻道
            url = ch.get('url', '') if isinstance(ch, dict) else ''  # 取網址
            is_fav = url in fav_urls  # 是否收藏

            item_widget = self._get_channel_row_widget(ch, i, is_fav)  # 建立卡片

            latencies = self.win.channel_latencies  # 取得延遲
            if url in latencies:  # 存在延遲
                self.update_latency_badge(item_widget, latencies[url])  # 更新標籤

            item = QListWidgetItem()  # 建立清單項
            item.setSizeHint(QSize(0, 65))  # 設定尺寸
            item.setData(Qt.ItemDataRole.UserRole, url)  # 綁定網址
            item.setData(Qt.ItemDataRole.UserRole + 1, ch)  # 綁定數據
            
            item_widget.mousePressEvent = lambda event, itm=item: self.on_channel_item_clicked(itm)  # 綁定點擊
            
            self.win.channel_list.addItem(item)  # 加入清單
            self.win.channel_list.setItemWidget(item, item_widget)  # 綁定卡片

        self.win.rendered_channel_count = end_idx  # 更新計數
        self.win.channel_list.setUpdatesEnabled(True)  # 解凍渲染

    def filter_channels(self):  # 篩選頻道
        if self.win.channel_list_mode == "live":  # 直播頁
            self.load_live_channels(reset=True)  # 重新加載
        else:  # 收藏/歷史/本地
            self.switch_channel_view(self.win.channel_list_mode)  # 重建目前視圖

    # ----- 分組/排序/過濾 -----
    def show_group_menu(self):  # 顯示分組
        menu = RoundedMenu(self.win)  # 建立選單
        
        raw_groups = [ch.get('group', '未分類') or '未分類' for ch in (self.win.all_channels_data or []) if isinstance(ch, dict)]  # 取分組名
        groups = ["全部分組"] + list(dict.fromkeys(raw_groups))  # 去重組合

        list_widget = QListWidget()  # 建立清單
        list_widget.setObjectName("group_menu_list")  # 🎯 僅保留 ID 讓 skin.py 統一接管樣式
        list_widget.setFrameShape(QFrame.Shape.NoFrame)  # 去除外框
        list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 按需滾動
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 關閉橫向

        for g_name in groups:  # 遍歷分組
            item = QListWidgetItem(g_name)  # 建立清單項
            item.setSizeHint(QSize(0, 32))  # 設定選項高度
            list_widget.addItem(item)  # 加入清單

        content_height = min(360, len(groups) * 36 + 10)  # 動態計算高度
        list_widget.setFixedSize(180, content_height)  # 固定高寬

        def _on_item_clicked(item):  # 點擊槽函數
            menu.close()  # 關閉選單
            self.filter_by_group(item.text())  # 執行過濾

        list_widget.itemClicked.connect(_on_item_clicked)  # 綁定點擊事件

        widget_action = QWidgetAction(menu)  # 包裹動作
        widget_action.setDefaultWidget(list_widget)  # 塞入清單
        menu.addAction(widget_action)  # 加入選單

        menu.exec(self.win.btn_group_menu.mapToGlobal(QPoint(0, self.win.btn_group_menu.height())))  # 彈出選單

    def filter_by_group(self, group_name):  # 依組過濾
        self.win.current_group_filter = group_name  # 設定當前
        display_text = group_name if len(group_name) <= 8 else group_name[:7] + "…"  # 截斷長度
        self.win.btn_group_menu.setText(f"{display_text} ▾")  # 設定按鈕
        self.win.filtered_channels_cache = []  # 🎯 清空快取確保重新載入
        self.load_live_channels(reset=True)  # 重新加載
        
    def show_sort_menu(self):  # 顯示排序
        menu = RoundedMenu(self.win)  # 建立選單
        sort_options = [  # 排序選項
            ("default", "預設排序"),
            ("latency_asc", "低延遲優先 ⚡"),
            ("name_asc", "名稱 A-Z"),
            ("name_desc", "名稱 Z-A")
        ]
        
        for mode_id, mode_label in sort_options:  # 遍歷選項
            action = QAction(mode_label, self.win)  # 建立動作
            action.triggered.connect(lambda _, m=mode_id, l=mode_label: self.set_sort_mode(m, l))  # 綁定觸發
            menu.addAction(action)  # 加入選單

        menu.exec(self.win.btn_sort_menu.mapToGlobal(QPoint(0, self.win.btn_sort_menu.height())))  # 彈出選單

    def set_sort_mode(self, mode, label):  # 設定排序
        self.win.current_sort_mode = mode  # 記錄模式
        self.win.btn_sort_menu.setText(f"{label} ▾")  # 更新按鈕
        
        current_view = self.win.channel_list_mode  # 取當前頁
        if current_view == 'live':  # 直播頁
            self.load_live_channels(reset=True)  # 刷直播
        else:  # 其他頁
            self.switch_channel_view(current_view)  # 刷視圖

    def set_quality_filter(self, quality, clicked_btn):  # 設定畫質
        self.win.current_quality = quality  # 記錄畫質
        for btn in self.win.filter_btn_list:  # 遍歷按鈕
            is_target = (btn == clicked_btn)  # 是否目標
            btn.setProperty("active", "true" if is_target else "false")  # 選中狀態
            btn.style().unpolish(btn)  # 取消樣式
            btn.style().polish(btn)  # 刷新樣式
        self.load_live_channels(reset=True)  # 重新加載

    # ----- 測速相關 -----
    def toggle_ping_test(self):  # 切換測速
        if self.is_pinging:  # 正在測速
            self.is_pinging = False  # 設為停止
            if self.ping_worker and self.ping_worker.isRunning():  # 線程運行
                self.ping_worker.is_stopped = True  # 設停止標誌
                self.ping_worker.quit()  # 退出線程
                self.ping_worker.wait(1000)  # 等待結束
            self.win.btn_ping_test.setText("測速⚡")  # 按鈕復原
            return  # 退出

        if not self.win.filtered_channels_cache:  # 確定性檢查測速對象
            return  # 放行退出

        self.is_pinging = True  # 設為測速
        self.win.btn_ping_test.setText("停止🛑")  # 按鈕變更
        
        if self.win.channel_latencies is None:  # 字典為空
            self.win.channel_latencies = {}  # 建立字典

        class PingWorker(QThread):  # 測速工作類
            progress = pyqtSignal(str, int)  # 進度訊號
            finished_signal = pyqtSignal()  # 完成訊號

            def __init__(self, channels):
                super().__init__()  # 初始化
                self.channels = channels  # 頻道列表
                self.is_stopped = False  # 停止標誌

            def run(self):  # 執行邏輯
                for ch in self.channels:  # 遍歷頻道
                    if self.is_stopped:  # 中途停止
                        break  # 中斷
                    url = ch.get('url', '')  # 取得網址
                    if not url or not url.startswith('http'):  # 非HTTP網址
                        continue  # 跳過
                    start = time.time()  # 記錄時間
                    try:
                        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})  # 建立HEAD
                        with urllib.request.urlopen(req, timeout=2.5):  # 發送請求
                            ms = int((time.time() - start) * 1000)  # 計算毫秒
                            if not self.is_stopped:  # 未停止
                                self.progress.emit(url, ms)  # 發射成功
                    except Exception:
                        if not self.is_stopped:  # 未停止
                            self.progress.emit(url, -1)  # 發射失敗
                self.finished_signal.emit()  # 發射完成
        
        def _on_ping_update(url, ms):  # 測速更新
            self.win.channel_latencies[url] = ms  # 寫入延遲
            for idx in range(self.win.channel_list.count()):  # 遍歷清單
                item = self.win.channel_list.item(idx)  # 取清單項
                if item and item.data(Qt.ItemDataRole.UserRole) == url:  # 匹配網址
                    widget = self.win.channel_list.itemWidget(item)  # 取卡片
                    if widget:  # 卡片存在
                        self.update_latency_badge(widget, ms)  # 刷新標籤
                    break  # 找到退出
        
        def _on_ping_finished():  # 測速結束
            self.is_pinging = False  # 設非測速
            self.win.btn_ping_test.setText("⚡ 測速")  # 復原按鈕
            if self.ping_worker:  # 線程存在
                self.ping_worker.quit()  # 退出線程
                self.ping_worker.wait(500)  # 等待釋放
                self.ping_worker.deleteLater()  # 安全刪除
                self.ping_worker = None  # 置空線程
        
        self.ping_worker = PingWorker(self.win.filtered_channels_cache)  # 實體化工作
        self.ping_worker.progress.connect(_on_ping_update)  # 連接更新
        self.ping_worker.finished_signal.connect(_on_ping_finished)  # 連接完成
        self.ping_worker.start()  # 啟動線程

    def update_latency_badge(self, item_widget, ms):  # 延遲標籤
        badge = item_widget.findChild(QLabel, "latency_badge")  # 尋找標籤
        if not badge:  # 未找到標籤
            badge = QLabel()  # 建立標籤
            badge.setObjectName("latency_badge")  # 設定名稱
            badge.setFixedHeight(22)  # 固定高度
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 文字置中
            layout = item_widget.layout()  # 取卡片佈局
            layout.insertWidget(layout.count() - 1, badge)  # 插入標籤

        if ms < 0 or ms >= 800:  # 超時或高延遲
            bg_color = "#ef4444"  # 紅色背景
            text = "FAIL" if ms < 0 else f"{ms}ms"  # 顯示文字
        elif 300 <= ms <= 799:  # 中等延遲
            bg_color = "#f59e0b"  # 黃色背景
            text = f"{ms}ms"  # 顯示毫秒
        else:  # 低延遲
            bg_color = "#10b981"  # 綠色背景
            text = f"{ms}ms"  # 顯示毫秒

        badge.setText(text)  # 設置內容
        badge.setStyleSheet(f"""
            QLabel#latency_badge {{
                background-color: {bg_color};
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                border-radius: 4px;
                padding: 2px 6px;
            }}
        """)  # 設置樣式

    # ----- 頻道點擊與EPG -----
    def on_channel_item_clicked(self, item):  # 頻道點擊
        if not item:  # 項目為空
            return  # 放行退出

        self.win.channel_list.setCurrentItem(item)  # 選中高亮

        url = item.data(Qt.ItemDataRole.UserRole) or ""  # 取出網址
        ch = item.data(Qt.ItemDataRole.UserRole + 1) or {}  # 取出物件
        name = ch.get('name', '') if isinstance(ch, dict) else item.text()  # 取出名稱
        clean_name = name.strip()  # 清理名稱

        current_epg = self._get_current_epg_title(ch) if isinstance(ch, dict) else ""  # 取EPG節目
        if not current_epg and isinstance(ch, dict):  # 備用EPG
            current_epg = ch.get('epg', '') or ch.get('current_program', '')  # 讀取備份

        self.win.current_channel_name = clean_name  # 寫入全域
        print(f"📌 [DEBUG] 頻道已點擊，寫入 current_channel_name: '{clean_name}', EPG: '{current_epg}'")  # 印出Log

        idx = self.win.active_player_index  # 活躍播放視窗
        if 0 <= idx < len(self.win.video_widgets):  # 索引合法
            w = self.win.video_widgets[idx]  # 取播放視窗
            w.channel_info = {'name': clean_name, 'url': url}  # 寫入資訊
            w.channel_url = url  # 寫入網址
            w.channel_name = clean_name  # 寫入名稱
            w.has_media = True  # 標記有媒體

        self.win.play_channel(item, custom_epg=current_epg, channel_name=clean_name)  # 播放頻道

    def _get_current_epg_title(self, ch):  # 取EPG標題
        """以索引查詢節目"""
        from epg_manager import channel_match_keys  # 歸一化鍵
        epg_cache = self.win.epg_lookup or self.win.epg_data or self.win.epg_cache  # 讀取快取
        if not epg_cache:  # 快取為空
            return ""  # 回傳空
        
        keys_to_check = set()  # 匹配鍵集
        if isinstance(ch, dict):  # 物件合法
            keys_to_check = channel_match_keys(ch.get('tvg_id'), ch.get('tvg_name'), ch.get('name'))  # 產生完整鍵集（含繁簡歸一化）

        for k in keys_to_check:  # 遍歷匹配鍵
            programmes = epg_cache.get(k)  # 讀取節目單
            if programmes:  # 節目存在
                for p in programmes:  # 遍歷時間段
                    try:
                        s_raw = p.get('start', '').split()[0][:14]  # 開始時間
                        e_raw = p.get('stop', '').split()[0][:14]  # 結束時間
                        if len(s_raw) >= 12:  # 長度合格
                            st = datetime.strptime(s_raw.ljust(14, '0'), "%Y%m%d%H%M%S")  # 轉為物件
                            et = datetime.strptime(e_raw.ljust(14, '0'), "%Y%m%d%H%M%S")  # 轉為物件
                            now = datetime.now()  # 當前時間
                            if st <= now <= et:  # 命中目前
                                return p.get('title', '')  # 傳回標題
                    except Exception:  # 時間解析錯
                        continue  # 繼續迴圈

        return ""  # 未命中空

    # 構建頻道行控件
    def _get_channel_row_widget(self, ch, i, is_fav):  # 建立頻道卡片
        """建構卡片圖卡"""
        item_widget = QWidget()  # 卡片組件
        
        iw_layout = QHBoxLayout(item_widget)  # 水平佈局
        iw_layout.setContentsMargins(0, 0, 0, 0)  # 外邊距
        iw_layout.setSpacing(10)  # 元素間距

        # 1. Logo Box
        logo_box = QLabel()  # 台徽圖框
        logo_box.setFixedSize(36, 26)  # 固定大小
        logo_box.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 垂直置中
        logo_box.setStyleSheet("background: transparent; border: none;")  # 透明背景
        logo_box.setText("")  # 清空內容

        import urllib.parse  # 網址解析
        logo_url = (ch.get('logo') or ch.get('tvg-logo') or ch.get('tvg_logo') or '') if isinstance(ch, dict) else ''  # 取圖標網址
        
        if not logo_url and isinstance(ch, dict):  # 無顯式網址
            raw_name = ch.get('tvg-name') or ch.get('tvg_name') or ch.get('name', '')  # 取得名稱
            clean_name = re.sub(r'(?i)(4k|fhd|hd|sd|hevc|60fps|\[.*?\]|\(.*?\))', '', raw_name).strip()  # 正則清洗
            
            if clean_name:  # 名稱有效
                logo_templates = self.win.current_logo_template or "https://live.fanmingming.cn/tv/{name}.png"  # 模板網址
                for tpl in logo_templates.split(','):  # 遍歷模板
                    tpl = tpl.strip()  # 清除空格
                    if '{name}' in tpl:  # 含有替換符
                        logo_url = tpl.replace('{name}', clean_name)  # 替換網址
                        break  # 中斷匹配

        pixmap_loaded = False  # 載入標誌

        if logo_url and logo_url.startswith('http'):  # 網路網址
            logo_dir = os.path.join(_script_dir, 'logo_cache')  # 固定專案/exe 目錄
            os.makedirs(logo_dir, exist_ok=True)  # 建立目錄
            logo_hash = hashlib.md5(logo_url.encode('utf-8')).hexdigest()  # 計算哈希
            logo_path = os.path.join(logo_dir, f"{logo_hash}.png")  # 快取路徑
            
            if os.path.exists(logo_path):  # 快取存在
                pixmap = QPixmap(logo_path)  # 讀取圖片
                if not pixmap.isNull():  # 圖片有效
                    rounded_pix = get_rounded_pixmap(pixmap, QSize(36, 26), radius=5)  # 圓角裁切
                    logo_box.setPixmap(rounded_pix)  # 設定圖片
                    pixmap_loaded = True  # 設載入成功
            else:  # 快取不存在
                if logo_url not in self._logo_download_set:  # 未在下載
                    self._logo_download_set.add(logo_url)  # 加入下載
                    worker = LogoFetchThread(logo_url, logo_path, logo_box)  # 建立工作線程
                    
                    def _on_logo_done(p, b):  # 完成回調
                        try:
                            pix = QPixmap(p)  # 載入圖片
                            if not pix.isNull():  # 圖片合法
                                b.setPixmap(get_rounded_pixmap(pix, QSize(36, 26), radius=5))  # 設定圖卡
                        except RuntimeError:  # 組件銷毀錯
                            pass  # 忽略異常
                        finally:
                            self._logo_download_set.discard(logo_url)  # 移除集合

                    worker.finished_signal.connect(_on_logo_done)  # 綁定訊號
                    self._logo_threads.append(worker)  # 保存線程
                    worker.start()  # 啟動線程

        if not pixmap_loaded:  # 未載入圖片
            if IconManager:  # 圖示管理器存在
                try:
                    tv_icon = IconManager.get_icon("tv", color="#8a8aa0", size=30)  # 取電視圖示
                    logo_box.setPixmap(tv_icon.pixmap(36, 26))  # 設圖片
                except Exception:
                    logo_box.setText("")  # 清空文字
            else:
                logo_box.setText("")  # 清空文字

        iw_layout.addWidget(logo_box)  # 加入佈局

        # 2. 文字佈局
        text_layout = QVBoxLayout()  # 垂直佈局
        text_layout.setSpacing(10)  # 文字間隔
        text_layout.setContentsMargins(0, 0, 0, 0)  # 清除外邊距

        name = ch.get('name', '未知頻道') if isinstance(ch, dict) else str(ch)  # 取得名稱
        group = ch.get('group', '') if isinstance(ch, dict) else ''  # 取得分組

        clean_name = re.sub(r'[^\w\s\u4e00-\u9fff]', '', name).strip()  # 去Emoji
        lbl_text = f"{i + 1:03d}   {clean_name}"  # 序號 + 名稱

        if group and group not in ['未分類', 'Undefined']:  # 有效分組
            lbl_text += f"   [{group}]"  # 拼接分組
        
        lbl_name = QLabel(lbl_text)  # 頻道標籤
        lbl_name.setProperty("role", "channel_label")  # 設置角色
        text_layout.addWidget(lbl_name)  # 加入佈局

        # 3. EPG 節目資訊
        current_prog = self._get_current_epg_title(ch) if isinstance(ch, dict) else ""  # 取EPG節目
        if not current_prog and isinstance(ch, dict):  # 備份EPG
            current_prog = ch.get('epg', '') or ch.get('current_program', '')  # 取備用內容

        if current_prog:  # 節目非空
            lbl_epg = QLabel(f"▶ {current_prog}")  # 節目標籤
            lbl_epg.setStyleSheet("color: #00f2fe; font-size: 12px; font-weight: 400; background: transparent;")  # 青色字體
            text_layout.addWidget(lbl_epg)  # 加入佈局

        iw_layout.addLayout(text_layout, stretch=1)  # 佈局伸展

        # 4. 收藏按鈕
        star_btn = QPushButton()  # 收藏按鈕
        star_btn.setText("")  # 清空文字
        star_btn.setFixedSize(30, 30)  # 固定尺寸
        star_btn.setProperty("role", "star_btn")  # 設定角色
        star_btn.setProperty("favorited", "true" if is_fav else "false")  # 收藏屬性
        star_btn.setCursor(Qt.CursorShape.PointingHandCursor)  # 手型鼠標

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
        """)  # 懸停半透明

        star_btn.setText("")  # 清空文字
        star_btn.setIcon(QIcon())  # 清除舊Icon
        
        self.win._set_btn_svg_icon(star_btn, "star_filled" if is_fav else "star_outline")  # 設定SVG圖示

        star_btn.clicked.connect(lambda checked=False, target_ch=ch, btn=star_btn: self.win.on_star_clicked(target_ch, btn))  # 點擊收藏

        iw_layout.addWidget(star_btn)  # 加入佈局
        return item_widget  # 回傳卡片

    # ----- 收藏/歷史/本地 -----
    def add_local_media_record(self, name_or_item, url: str = None):  # 增加本地紀錄
        if not self.win.local_media_list:  # 列表為空
            self.win.local_media_list = []  # 初始化列表
        
        new_items = []  # 新項目列表
        if isinstance(name_or_item, list):  # 傳入列表
            for item in name_or_item:  # 遍歷列表
                if isinstance(item, dict):  # 字典項目
                    new_items.append(item)  # 加入項目
                elif isinstance(item, str):  # 路徑項目
                    new_items.append({'name': os.path.basename(item), 'url': item})  # 轉字典加入
        elif isinstance(name_or_item, dict):  # 傳入字典
            new_items.append(name_or_item)  # 加入字典
        elif isinstance(name_or_item, str):  # 傳入字串
            item_url = url if url else name_or_item  # 取出網址
            item_name = name_or_item if url else os.path.basename(name_or_item)  # 取出名稱
            new_items.append({'name': item_name, 'url': item_url})  # 加入項目

        if not new_items:  # 無新項目
            return  # 退出

        new_urls = {x.get('url') for x in new_items if isinstance(x, dict)}  # 新網址集
        filtered_old = [  # 過濾舊紀錄
            x for x in self.win.local_media_list 
            if isinstance(x, dict) and x.get('url') not in new_urls
        ]

        self.win.local_media_list = new_items + filtered_old  # 合併記錄

        target_btn = None  # 尋找目標鈕
        for btn in self.win.sidebar_btns:  # 遍歷按鈕
            if btn.toolTip() == "本地媒體":  # 匹配提示
                target_btn = btn  # 保存按鈕
                break  # 中斷
                    
        self.switch_channel_view("local", target_btn)  # 切換至本地

    def remove_history_or_local_item(self, ch, item, mode):  # 移除單項
        attr_name = 'history_sources' if mode == 'history' else 'local_media_list'  # 取屬性名
        target_list = getattr(self.win, attr_name, [])  # 取對應清單
        if ch in target_list:  # 項目在列表中
            target_list.remove(ch)  # 移除項目
        row = self.win.channel_list.row(item)  # 取得行號
        if row >= 0:  # 行號合法
            self.win.channel_list.takeItem(row)  # 清除行項目
        if mode == 'history':  # 歷史模式
            self.win.save_history()  # 儲存歷史紀錄

    def clear_playlist(self, mode):  # 清空播放清單
        attr_name = 'history_sources' if mode == 'history' else 'local_media_list'  # 取屬性名
        setattr(self.win, attr_name, [])  # 重設為空
        if mode == 'history':  # 歷史模式
            self.win.save_history()  # 寫入歷史檔
        self.switch_channel_view(mode)  # 刷新視圖

    def show_channel_list_context_menu(self, pos):  # 右鍵菜單
        mode = self.win.channel_list_mode  # 取當前模式
        if mode not in ["history", "local"]:  # 不支援頁面
            return  # 退出

        menu = RoundedMenu(self.win)  # 建立圓角菜單
        clear_label = "🗑️ 一鍵清空最近播放" if mode == "history" else "🗑️ 一鍵清空本地媒體"  # 設定文字
        action = QAction(clear_label, self.win)  # 建立菜單動作
        action.triggered.connect(lambda: self.clear_playlist(mode))  # 綁定清空
        menu.addAction(action)  # 加入菜單
        menu.exec(self.win.channel_list.mapToGlobal(pos))  # 彈出選單

    # ----- EPG載入 -----
    def load_epg_data(self, epg_urls_str):  # 載入EPG
        print(f"📡 [DEBUG] 收到 EPG 載入請求，原始網址字串: '{epg_urls_str}'")  # 印出Log

        if not epg_urls_str or not epg_urls_str.strip():  # 網址為空
            print("⚠️ [DEBUG] EPG 網址為空，取消載入")  # 印出警示
            return  # 退出

        urls = [u.strip() for u in epg_urls_str.split(',') if u.strip()]  # 切割網址
        print(f"🔍 [DEBUG] 解析出 {len(urls)} 個有效 EPG 網址: {urls}")  # 印出解析

        if urls:  # 網址存在
            print(f"🚀 [DEBUG] 已轉交 main_window.load_epg 處理（{len(urls)} 個來源）")  # 轉發Log
            self.win.load_epg(','.join(urls))  # 執行加載（全部來源）
        else:  # 轉發失敗
            print("❌ [DEBUG] 轉交失敗，找不到 self.win.load_epg")  # 失敗Log
# [代碼終點] ...