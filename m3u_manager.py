# m3u_manager.py
from config import *

# ==================== M3U 異步解析引擎 ====================
class M3UFetchWorker(QThread):
    finished_signal = pyqtSignal(list, str)  # 📌 修改：額外傳出自動提取到的 EPG 網址 (channels, epg_url)
    progress_signal = pyqtSignal(int, int)

    def __init__(self, source):
        super().__init__()
        self.source = source

    def run(self):
        channels = []
        extracted_epg_url = ""
        def extract_attr(line, attr_name):
            start_str = f'{attr_name}="'
            start = line.find(start_str)
            if start == -1:
                return ''
            start += len(start_str)
            end = line.find('"', start)
            return line[start:end] if end != -1 else ''

        response = None
        try:
            if self.source.startswith('http'):
                req = urllib.request.Request(self.source, headers={'User-Agent': 'Mozilla/5.0'})
                response = urllib.request.urlopen(req, timeout=15)
                lines = [line.decode('utf-8', errors='ignore') for line in response]
            else:
                response = open(self.source, 'r', encoding='utf-8', errors='ignore')
                lines = response.readlines()

            total_lines = len(lines)
            current_channel = {}
            last_percent = -1
            for idx, line in enumerate(lines):
                if total_lines > 0:
                    percent = int(((idx + 1) / total_lines) * 100)
                    if percent != last_percent:
                        self.progress_signal.emit(idx + 1, total_lines)
                        last_percent = percent

                line = line.strip()
                if not line:
                    continue
                
                # 📌 新增：提取標頭中的 x-tvg-url / url-tvg (EPG 鏈接) 並自動將 m3u4u / .gz 修正為 .xml
                if line.startswith('#EXTM3U'):
                    extracted_epg_url = extract_attr(line, 'x-tvg-url') or extract_attr(line, 'url-tvg')
                    if extracted_epg_url:
                        # 1. 自動把 m3u4u 的 /epg/ 轉成純 XML 的 /xml/
                        extracted_epg_url = re.sub(r'm3u4u\.com/epg/', '[m3u4u.com/xml/](https://m3u4u.com/xml/)', extracted_epg_url)
                        # 2. 自動去除去掉結尾的 .gz (如果有)
                        if extracted_epg_url.endswith('.gz'):
                            extracted_epg_url = extracted_epg_url[:-3]
                    
                elif line.startswith('#EXTINF'):
                    logo = extract_attr(line, 'tvg-logo')
                    group = extract_attr(line, 'group-title') or '未分類'
                    tvg_id = extract_attr(line, 'tvg-id')  # 📌 提取 tvg-id 供 EPG 對應
                    tvg_name = extract_attr(line, 'tvg-name')  # 🎯 新增：提取 tvg-name 屬性
                    
                    comma_idx = line.rfind(',')
                    raw_name = line[comma_idx + 1:].strip() if comma_idx != -1 else ''
                    
                    # 🎯 名稱優先順序：逗號後的顯示名稱 > tvg_name 屬性 > Unknown
                    name = raw_name or tvg_name or 'Unknown'
                    
                    current_channel = {
                        'logo': logo, 
                        'group': group, 
                        'name': name, 
                        'tvg_id': tvg_id,
                        'tvg_name': tvg_name  # 🎯 補上 tvg_name 鍵，避免 main_window 讀取時拿到 None
                    }
                    
                elif not line.startswith('#') and current_channel:
                    current_channel['url'] = line
                    if 'name' in current_channel:
                        channels.append(current_channel)
                    current_channel = {}

        except Exception as e:
            print(f"Error: 載入 M3U 失敗 - {e}")
            channels = []
        finally:
            if response and hasattr(response, 'close'):
                response.close()

        self.finished_signal.emit(channels, extracted_epg_url)

# ==================== M3U 管理 UI 組件 ====================
class M3U播放清單管理界面(QFrame):
    def __init__(self, name, url, is_local=False, is_active=False, parent=None, accent="#a855f7", border="#581c87", bg_panel="#121520"):
        super().__init__(parent)
        self.is_local = is_local
        self.accent = accent
        self.border_color = border
        self.bg_panel = bg_panel
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("m3u_item_frame")
        self.setFixedHeight(64)
        # 🎯 設置最小寬度，當父容器太窄時觸發橫向 Scrollbar
        self.setMinimumWidth(450)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(10)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_lbl = QLabel(name)
        self.title_lbl.setObjectName("m3u_item_title")

        # 🎯 網址 Label 設置：自動截斷 + ToolTip 懸停查看完整 URL
        self.url_lbl = QLabel(url)
        self.url_lbl.setObjectName("m3u_item_url")
        self.url_lbl.setToolTip(url)

        info_layout.addWidget(self.title_lbl)
        info_layout.addWidget(self.url_lbl)
        layout.addLayout(info_layout, stretch=1)

        badge_layout = QHBoxLayout()
        badge_layout.setSpacing(6)
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        badge_type = "本地" if is_local else "URL"
        self.badge_lbl = QLabel(badge_type)
        self.badge_lbl.setObjectName("m3u_item_badge")
        
        badge_layout.addWidget(self.badge_lbl)

        self.star_lbl = QLabel("⭐")
        self.star_lbl.setObjectName("m3u_item_star")
        badge_layout.addWidget(self.star_lbl)

        layout.addLayout(badge_layout)
        self.set_active(is_active)

    def set_active(self, is_active):
        self.is_active = is_active
        self.star_lbl.setVisible(is_active)
        
        # 📌 配合 skin.py 的屬性選擇器驅動，利用動態屬性控制外觀狀態
        self.setProperty("active", "true" if is_active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        
        # 已移除原本寫死的 self.setStyleSheet(...)，全面交由 skin.py 統一管理

class M3U播放列表管理彈窗(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(400)

class 添加網址對話框(M3U播放列表管理彈窗):
    def __init__(self, parent=None):
        super().__init__("添加網絡鏈接", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(QLabel("訂閱名稱"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("請輸入訂閱名稱 (如：IPTV / Live)")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("M3U 網址"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://或 https://...")
        layout.addWidget(self.url_input)

        # 🎯 新增：EPG 網址輸入框
        layout.addWidget(QLabel("EPG 地址 (使用逗號合併多個 EPG):"))
        self.epg_input = QLineEdit()
        self.epg_input.setPlaceholderText("http://example.com/epg.xml")
        layout.addWidget(self.epg_input)
        
        # 🎯 新增：台徽推送/範本網址輸入框 (支援 {name} 與逗號分隔)
        layout.addWidget(QLabel("台徽推送範本 (使用逗號分隔多個，支援 {name} 自動匹配):"))
        self.logo_input = QLineEdit()
        self.logo_input.setPlaceholderText("https://live.fanmingming.cn/tv/{name}.png")
        self.logo_input.setText("https://live.fanmingming.cn/tv/{name}.png")
        layout.addWidget(self.logo_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("確定"); ok_btn.setProperty("class", "confirm-btn")
        cancel_btn = QPushButton("取消"); cancel_btn.setProperty("class", "cancel-btn")
        ok_btn.clicked.connect(self.accept); cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn); btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

class 添加Xtream對話框(M3U播放列表管理彈窗):
    def __init__(self, parent=None):
        super().__init__("添加 Xtream 代碼", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        layout.addWidget(QLabel("訂閱名稱"))
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("服務器 URL"))
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("http://example.com:8080")
        layout.addWidget(self.server_input)

        layout.addWidget(QLabel("用戶名"))
        self.user_input = QLineEdit()
        layout.addWidget(self.user_input)

        layout.addWidget(QLabel("密碼"))
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pass_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("確定"); ok_btn.setProperty("class", "confirm-btn")
        cancel_btn = QPushButton("取消"); cancel_btn.setProperty("class", "cancel-btn")
        ok_btn.clicked.connect(self.accept); cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn); btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
    def get_data(self):
        name = self.name_input.text().strip() or "Xtream IPTV"
        srv = self.server_input.text().strip().rstrip('/')
        usr = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()
        generated_url = f"{srv}/get.php?username={usr}&password={pwd}&type=m3u_plus&output=ts"
        return {'name': name, 'url': generated_url}

class 編輯來源對話框(M3U播放列表管理彈窗):
    def __init__(self, name="", url="", epg_url="", logo_url="", parent=None):
        super().__init__("編輯訂閱網址", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(QLabel("訂閱名稱"))
        self.name_input = QLineEdit(name)
        self.name_input.setPlaceholderText("例如：自訂頻道 / IPTV")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("訂閱網址 / 本地M3U文件路徑"))
        self.url_input = QLineEdit(url)
        self.url_input.setPlaceholderText("https://... 或本地 .m3u 路徑")
        layout.addWidget(self.url_input)

        # 🎯 新增：EPG 網址編輯輸入框
        layout.addWidget(QLabel("EPG 地址 (使用逗號合併多個 EPG):"))
        self.epg_input = QLineEdit(epg_url)
        self.epg_input.setPlaceholderText("http://example.com/epg.xml")
        layout.addWidget(self.epg_input)
        
        # 🎯 新增：台徽推送/範本網址輸入框 (支援 {name} 與逗號分隔)
        layout.addWidget(QLabel("台徽推送範本 (使用逗號分隔多個，支援 {name} 自動匹配):"))
        self.logo_input = QLineEdit()
        self.logo_input.setPlaceholderText("https://live.fanmingming.cn/tv/{name}.png")
        self.logo_input.setText(logo_url or "https://live.fanmingming.cn/tv/{name}.png")
        layout.addWidget(self.logo_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("確定"); ok_btn.setProperty("class", "confirm-btn")
        cancel_btn = QPushButton("取消"); cancel_btn.setProperty("class", "cancel-btn")
        ok_btn.clicked.connect(self.accept); cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn); btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_data(self):
        return (
            self.name_input.text().strip(),
            self.url_input.text().strip(),
            self.epg_input.text().strip(),
            self.logo_input.text().strip()
        )

class M3U管理器主視窗(QDialog):
    def __init__(self, parent=None, sources=None, current_url=None):
        super().__init__(parent)
        self.setWindowTitle("M3U管理器主視窗")
        self.resize(720, 500)
        self.parent_win = parent
        self.sources = [dict(s) for s in sources] if sources else []
        self.selected_url = current_url

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_icon = QLabel("📁")
        header_icon.setStyleSheet("font-size: 22px;")
        
        header_text_layout = QVBoxLayout()
        title_lbl = QLabel("M3U管理器主視窗")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #fff;")
        sub_lbl = QLabel("管理你的 IPTV 頻道列表與播放源。")
        sub_lbl.setStyleSheet("font-size: 11px; color: #888899;")
        
        header_text_layout.addWidget(title_lbl)
        header_text_layout.addWidget(sub_lbl)
        header_layout.addWidget(header_icon)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  搜尋播放列表...")
        self.search_input.textChanged.connect(self.refresh_list)
        main_layout.addWidget(self.search_input)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)

        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        
        # 🎯 徹底殺死 Qt 原生選中高亮（防止綠色透出）
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # 🎯 開啟像素級橫向滾動支援
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        content_layout.addWidget(self.list_widget, stretch=3)

        action_layout = QVBoxLayout()
        action_layout.setSpacing(8)
        
        self.action_title = QLabel("操作")
        action_layout.addWidget(self.action_title)

        btn_add_file = QPushButton("➕  添加文件")
        btn_add_file.setProperty("class", "action-btn")
        btn_add_file.clicked.connect(self.add_file)
        
        btn_add_url = QPushButton("🌐  添加鏈接")
        btn_add_url.setProperty("class", "action-btn")
        btn_add_url.clicked.connect(self.add_url)
        
        btn_add_xtream = QPushButton("🔑  添加 Xtream")
        btn_add_xtream.setProperty("class", "action-btn")
        btn_add_xtream.clicked.connect(self.add_xtream)
        
        btn_edit = QPushButton("✏️  編輯")
        btn_edit.setProperty("class", "action-btn")
        btn_edit.clicked.connect(self.edit_source)
        
        btn_del = QPushButton("🗑️  刪除")
        btn_del.setProperty("class", "danger-btn")
        btn_del.clicked.connect(self.delete_source)

        action_layout.addWidget(btn_add_file)
        action_layout.addWidget(btn_add_url)
        action_layout.addWidget(btn_add_xtream)
        action_layout.addWidget(btn_edit)
        action_layout.addWidget(btn_del)
        action_layout.addStretch()
        
        content_layout.addLayout(action_layout, stretch=1)
        main_layout.addLayout(content_layout, stretch=1)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        ok_btn = QPushButton("確定")
        ok_btn.setProperty("class", "confirm-btn")
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("class", "cancel-btn")
        cancel_btn.clicked.connect(self.reject)

        bottom_layout.addWidget(ok_btn)
        bottom_layout.addWidget(cancel_btn)
        main_layout.addLayout(bottom_layout)

        self.update_dynamic_theme()
        self.refresh_list()

    def update_dynamic_theme(self):
        accent = "#a855f7"
        border = "#581c87"
        bg_main = "#0b0c10"
        bg_panel = "#121520"

        if self.parent_win and hasattr(self.parent_win, 'current_theme_config'):
            c = self.parent_win.current_theme_config
            accent = c.get('accent', accent)
            border = c.get('border', border)
            bg_main = c.get('bg_main', bg_main)
            bg_panel = c.get('bg_panel', bg_panel)

        self.theme_accent = accent
        self.theme_border = border
        self.theme_bg_panel = bg_panel

        # 📌 同步主視窗樣式，全面交由 skin.py 統一控管
        if self.parent_win and hasattr(self.parent_win, 'styleSheet'):
            self.setStyleSheet(self.parent_win.styleSheet())

        if hasattr(self, 'action_title'):
            self.action_title.setStyleSheet(f"color: {accent}; font-weight: bold; font-size: 12px; margin-bottom: 4px;")

    def get_data(self):
        return self.sources, self.selected_url

    def refresh_list(self):
        while self.list_widget.count() > 0:
            item = self.list_widget.takeItem(0)
            widget = self.list_widget.itemWidget(item)
            if widget:
                widget.deleteLater()
            del item

        self.list_widget.clear()
        filter_text = self.search_input.text().strip().lower()

        accent = getattr(self, 'theme_accent', '#a855f7')
        border = getattr(self, 'theme_border', '#581c87')
        bg_panel = getattr(self, 'theme_bg_panel', '#121520')

        for src in self.sources:
            name = src.get('name', '未命名')
            url = src.get('url', '')
            is_local = url.lower().endswith(('m3u', 'm3u8', 'txt')) and not url.lower().startswith(('http://', 'https://'))
            is_active = (url == self.selected_url)

            if filter_text and (filter_text not in name.lower() and filter_text not in url.lower()):
                continue

            card = M3U播放清單管理界面(
                name, url, 
                is_local=is_local, 
                is_active=is_active, 
                accent=accent, 
                border=border, 
                bg_panel=bg_panel
            )
            item = QListWidgetItem()
            
            # 🎯 核心重點：計算內容所需的最小寬度，強制傳給 QListWidgetItem
            # 500px 確保超長 URL 必定會觸發橫向滾動條！
            item.setSizeHint(QSize(460, 72))
            item.setData(Qt.ItemDataRole.UserRole, src)

            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, card)

            if is_active:
                self.list_widget.setCurrentItem(item)

    def on_selection_changed(self):
        selected_item = self.list_widget.currentItem()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            card = self.list_widget.itemWidget(item)
            if card:
                card.set_active(item == selected_item)
        if selected_item:
            src = selected_item.data(Qt.ItemDataRole.UserRole)
            self.selected_url = src.get('url')

    def add_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "選擇 M3U 播放列表檔", "", "M3U Files (*.m3u *.m3u8 *.txt);;All Files (*)")
        if file_path:
            dlg = 編輯來源對話框(name="本地播放列表", url=file_path, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                name = dlg.name_input.text().strip() or "本地播放列表"
                url = dlg.url_input.text().strip()
                if url:
                    self.sources.append({'name': name, 'url': url})
                    self.refresh_list()

    def add_url(self):
        dlg = 添加網址對話框(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = dlg.name_input.text().strip() or "網絡訂閱"
            url = dlg.url_input.text().strip()
            epg = dlg.epg_input.text().strip()  # 📌 修復：保存 EPG 輸入框的內容
            logo = dlg.logo_input.text().strip() # 🎯 補上保存台徽範本網址
            if url:
                self.sources.append({'name': name, 'url': url, 'epg': epg, 'logo': logo})
                self.refresh_list()

    def add_xtream(self):
        dlg = 添加Xtream對話框(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data:
                self.sources.append(data)
                self.refresh_list()

    def edit_source(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.sources):
            return
            
        src = self.sources[row]
        # 🎯 傳入原有的 epg 與 logo 網址
        dlg = 編輯來源對話框(name=src.get('name', ''), url=src.get('url', ''), epg_url=src.get('epg', ''), logo_url=src.get('logo', ''), parent=self)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # 🎯 完整解包 4 個返回值 (名稱, URL, EPG, Logo)，徹底解決崩潰
            new_name, new_url, new_epg, new_logo = dlg.get_data()
            self.sources[row]['name'] = new_name or "未命名訂閱"
            self.sources[row]['url'] = new_url
            self.sources[row]['epg'] = new_epg
            self.sources[row]['logo'] = new_logo
            
            if self.selected_url == src.get('url'):
                self.selected_url = new_url
            self.refresh_list()

    def delete_source(self):
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.sources):
            self.sources.pop(row)
            self.refresh_list()