# [代碼起點]
from config import *  # 匯入配置

from urllib.parse import unquote, quote  # 匯入解碼/編碼
import re  # 匯入正則
import urllib.request  # 網路請求

def parse_xtream_url(url):  # 解析網址
    """解析 Xtream URL，回傳 {'server', 'username', 'password'} 或 None（帳密已做 URL 解碼）"""
    # 提取基礎伺服器 (scheme://host:port)
    server_match = re.match(r'(https?://[^/]+)', url or '')  # 比對伺服
    if not server_match:  # 未能匹配
        return None  # 回傳無值
    server = server_match.group(1)  # 取得伺服

    def _grab_value(key):  # 抓取參數
        match = re.search(r'[?&]' + key + r'=([^&]+)', url)  # 匹配參數
        return unquote(match.group(1)) if match else None  # 回傳解碼值

    # 提取用戶名同密碼（自動 URL 解碼，例如 %40 → @）
    username = _grab_value('username')  # 匹配帳號
    password = _grab_value('password')  # 匹配密碼
    if username is not None and password is not None:  # 兩者皆有
        return {'server': server, 'username': username, 'password': password}  # 回傳字典
    return None  # 回傳無值

def _clean_epg_entry(entry):  # 清理單條EPG
    """單條 EPG 網址修正：m3u4u /epg/ → /xml/，並移除尾端 .gz"""
    entry = (entry or '').strip()  # 去除空格
    if not entry:  # 空值
        return ''  # 回傳空字
    entry = re.sub(r'm3u4u\.com/epg/', 'm3u4u.com/xml/', entry)  # 修正路徑
    if entry.lower().endswith('.gz'):  # 壓縮檔
        entry = entry[:-3]  # 去除副檔
    return entry.strip()  # 回傳結果

# ==================== M3U 異步解析引擎 ====================
class M3UFetchWorker(QThread):  # 異步線程
    finished_signal = pyqtSignal(list, str)  # 完成訊號
    progress_signal = pyqtSignal(int, int)  # 進度訊號
    error_signal = pyqtSignal(str)  # 錯誤訊號

    def __init__(self, source):  # 初始化
        super().__init__()  # 呼叫父類
        self.source = source  # 設定來源

    @staticmethod
    def _decode_playlist(raw_data):  # 解碼播放列表
        """優先 UTF-8（含 BOM），再試 GB18030 / Big5，最後寬容解碼。"""
        for encoding in ("utf-8-sig", "gb18030", "big5"):  # 常見編碼
            try:  # 嘗試解碼
                return raw_data.decode(encoding)  # 成功回傳
            except UnicodeDecodeError:  # 換下一種
                continue  # 繼續
        return raw_data.decode("utf-8", errors="replace")  # 最後寬容處理

    def run(self):  # 執行線程
        channels = []  # 頻道列表
        extracted_epg_url = ""  # 節目網址
        def extract_attr(line, attr_name):  # 抓取屬性
            start_str = f'{attr_name}="'  # 起始標籤
            start = line.find(start_str)  # 尋找開頭
            if start == -1:  # 未能找到
                return ''  # 回傳空字
            start += len(start_str)  # 計算位置
            end = line.find('"', start)  # 尋找結尾
            return line[start:end] if end != -1 else ''  # 擷取屬性

        response = None  # 回應物件
        try:  # 嘗試執行
            if self.source.startswith('http'):  # 網絡訂閱
                req = urllib.request.Request(self.source, headers={'User-Agent': 'Mozilla/5.0'})  # 建立請求
                response = urllib.request.urlopen(req, timeout=15)  # 開啟網址
                raw_data = response.read()  # 讀取位元組
            else:  # 本地檔案
                with open(self.source, 'rb') as f:  # 二進位讀取
                    raw_data = f.read()  # 讀取全文
            lines = self._decode_playlist(raw_data).splitlines()  # 自動判斷編碼

            total_lines = len(lines)  # 計算總行
            current_channel = {}  # 當前頻道
            last_percent = -1  # 上次進度
            for idx, line in enumerate(lines):  # 逐行解析
                if total_lines > 0:  # 總行有效
                    percent = int(((idx + 1) / total_lines) * 100)  # 計算百分
                    if percent != last_percent:  # 進度變動
                        self.progress_signal.emit(idx + 1, total_lines)  # 發送進度
                        last_percent = percent  # 更新百分

                line = line.strip()  # 去除空格
                if not line:  # 空白行
                    continue  # 跳過不理
                
                # 📌 提取標頭中的 x-tvg-url / url-tvg（EPG 鏈接），逐條修正後以逗號合併，供 load_epg_data 拆分
                if line.startswith('#EXTM3U'):  # M3U標頭
                    raw_epg_value = extract_attr(line, 'x-tvg-url') or extract_attr(line, 'url-tvg')  # 抓取EPG
                    if raw_epg_value:  # 有EPG網址
                        # 支援多個 EPG（逗號分隔）：每個都做 m3u4u / .gz 修正，再合併回逗號字串
                        extracted_epg_url = ','.join(
                            e for e in (_clean_epg_entry(p) for p in raw_epg_value.split(',')) if e
                        )  # 合併EPG
                    
                elif line.startswith('#EXTINF'):  # 頻道資訊
                    logo = extract_attr(line, 'tvg-logo')  # 抓取台徽
                    group = extract_attr(line, 'group-title') or '未分類'  # 抓取群組
                    tvg_id = extract_attr(line, 'tvg-id')  # 抓取ID
                    tvg_name = extract_attr(line, 'tvg-name')  # 抓取名稱
                    
                    comma_idx = line.rfind(',')  # 尋找逗號
                    raw_name = line[comma_idx + 1:].strip() if comma_idx != -1 else ''  # 截取檔名
                    
                    # 🎯 名稱優先順序：逗號後的顯示名稱 > tvg_name 屬性 > Unknown
                    name = raw_name or tvg_name or 'Unknown'  # 決定名稱
                    
                    current_channel = {
                        'logo': logo, 
                        'group': group, 
                        'name': name, 
                        'tvg_id': tvg_id,
                        'tvg_name': tvg_name  # 標註名稱
                    }  # 暫存頻道
                    
                elif not line.startswith('#') and current_channel:  # 播放網址
                    current_channel['url'] = line  # 寫入網址
                    if 'name' in current_channel:  # 名稱存在
                        channels.append(current_channel)  # 加入列表
                    current_channel = {}  # 重置頻道

        except Exception as e:  # 發生例外
            print(f"Error: 載入 M3U 失敗 - {e}")  # 印出錯誤
            channels = []  # 清空頻道
            self.error_signal.emit(str(e))  # 通知錯誤
        finally:  # 最終執行
            if response and hasattr(response, 'close'):  # 物件可關
                response.close()  # 關閉連線

        self.finished_signal.emit(channels, extracted_epg_url)  # 發送結果

# ==================== M3U 管理 UI 組件 ====================
class M3U管理主視窗(QDialog):  # 管理主窗
    def __init__(self, parent=None, sources=None, current_url=None):  # 初始化
        super().__init__(parent)  # 呼叫父類
        self.setWindowTitle("M3U管理主視窗")  # 設定標題
        self.resize(720, 500)  # 調整大小
        self.parent_win = parent  # 綁定父窗
        self.sources = [dict(s) for s in sources] if sources else []  # 複製來源
        # 根據 current_url 搵對應索引
        self.selected_index = -1  # 預設索引
        if current_url:  # 有當前網址
            for i, src in enumerate(self.sources):  # 搜尋索引
                if src.get('url') == current_url:  # 網址匹配
                    self.selected_index = i  # 設定索引
                    break  # 跳出迴圈

        # 🔒 更新標誌，防止信號互相干擾
        self._updating = False  # 鎖定標誌

        main_layout = QVBoxLayout(self)  # 主版面
        main_layout.setContentsMargins(20, 20, 20, 20)  # 設定邊距
        main_layout.setSpacing(12)  # 間距設定

        header_layout = QHBoxLayout()  # 頁首版面
        header_icon = QLabel("📁")  # 圖示標籤
        header_icon.setStyleSheet("font-size: 22px;")  # 圖示字型
        
        header_text_layout = QVBoxLayout()  # 文字版面
        title_lbl = QLabel("M3U管理主視窗")  # 主標題
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #fff;")  # 標題樣式
        sub_lbl = QLabel("管理你的 IPTV 頻道列表與播放源。")  # 副標題
        sub_lbl.setStyleSheet("font-size: 11px; color: #888899;")  # 副標樣式
        
        header_text_layout.addWidget(title_lbl)  # 加入主標
        header_text_layout.addWidget(sub_lbl)  # 加入副標
        header_layout.addWidget(header_icon)  # 加入圖示
        header_layout.addLayout(header_text_layout)  # 加入文字
        header_layout.addStretch()  # 填滿餘白
        main_layout.addLayout(header_layout)  # 加入頁首

        self.search_input = QLineEdit()  # 搜尋框
        self.search_input.setPlaceholderText("🔍  搜尋播放列表...")  # 預設文字
        self.search_input.textChanged.connect(self.refresh_list)  # 文字變動
        main_layout.addWidget(self.search_input)  # 加入搜尋

        content_layout = QHBoxLayout()  # 內容版面
        content_layout.setSpacing(15)  # 間距設定

        self.list_widget = QListWidget()  # 列表組件
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 關閉焦點
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)  # 單選模式
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)  # 選項變更
        
        # 🎯 徹底殺死 Qt 原生選中高亮（防止綠色透出）

        
        # 🎯 開啟像素級橫向滾動支援
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 橫向滾條
        self.list_widget.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)  # 像素滾動
        
        content_layout.addWidget(self.list_widget, stretch=3)  # 加入列表

        action_layout = QVBoxLayout()  # 按鈕版面
        action_layout.setSpacing(8)  # 間距設定
        

        
        #右側按鈕
        btn_add_file = QPushButton("➕  添加文件")  # 檔按鈕
        btn_add_file.setProperty("class", "action-btn")  # 設定類別
        btn_add_file.clicked.connect(self.add_file)  # 點擊加檔
        
        btn_add_url = QPushButton("🌐  添加鏈接")  # 網按鈕
        btn_add_url.setProperty("class", "action-btn")  # 設定類別
        btn_add_url.clicked.connect(self.add_url)  # 點擊加網
        
        btn_add_xtream = QPushButton("🔑  添加 Xtream")  # 碼按鈕
        btn_add_xtream.setProperty("class", "action-btn")  # 設定類別
        btn_add_xtream.clicked.connect(self.add_xtream)  # 點擊加碼
        
        btn_edit = QPushButton("✏️  編輯")  # 編按鈕
        btn_edit.setProperty("class", "action-btn")  # 設定類別
        btn_edit.clicked.connect(self.edit_source)  # 點擊編輯
        
        btn_del = QPushButton("🗑️  刪除")  # 刪按鈕
        btn_del.setProperty("class", "danger-btn")  # 設定類別
        btn_del.clicked.connect(self.delete_source)  # 點擊刪除

        action_layout.addWidget(btn_add_file)  # 加入按鈕
        action_layout.addWidget(btn_add_url)  # 加入按鈕
        action_layout.addWidget(btn_add_xtream)  # 加入按鈕
        action_layout.addWidget(btn_edit)  # 加入按鈕
        action_layout.addWidget(btn_del)  # 加入按鈕
        action_layout.addStretch()  # 填滿餘白
        
        content_layout.addLayout(action_layout, stretch=1)  # 加入按鈕
        main_layout.addLayout(content_layout, stretch=1)  # 加入內容

        bottom_layout = QHBoxLayout()  # 底部版面
        bottom_layout.addStretch()  # 填滿餘白

        ok_btn = QPushButton("確定")  # 確按鈕
        ok_btn.setProperty("class", "confirm-btn")  # 設定類別
        ok_btn.clicked.connect(self.accept)  # 點擊確認
        
        cancel_btn = QPushButton("取消")  # 取按鈕
        cancel_btn.setProperty("class", "cancel-btn")  # 設定類別
        cancel_btn.clicked.connect(self.reject)  # 點擊取消

        bottom_layout.addWidget(ok_btn)  # 加入確定
        bottom_layout.addWidget(cancel_btn)  # 加入取消
        main_layout.addLayout(bottom_layout)  # 加入底部

        self.update_dynamic_theme()  # 套用主題
        self.refresh_list()  # 刷清列表

    def _index_of(self, src):  # 定位來源
        """用物件身份定位來源索引；找不到時才退回 name+url 內容比對（避免重複項誤判）"""
        if not isinstance(src, dict):  # 非法輸入
            return -1  # 回傳無值
        for i, s in enumerate(self.sources):  # 身份比對
            if s is src:  # 同一物件
                return i  # 回傳索引
        for i, s in enumerate(self.sources):  # 內容比對
            if s.get('url') == src.get('url') and s.get('name') == src.get('name'):  # 資料一致
                return i  # 回傳索引
        return -1  # 回傳無值

    def update_dynamic_theme(self):  # 主題更新
        accent = "#a855f7"  # 強調色彩
        border = "#581c87"  # 邊框色彩
        bg_main = "#0b0c10"  # 主背景色
        bg_panel = "#121520"  # 面板背景

        if self.parent_win:  # 有父視窗
            c = self.parent_win.current_theme_config  # 取得設定
            accent = c.get('accent', accent)  # 讀取主色
            border = c.get('border', border)  # 讀取邊框
            bg_main = c.get('bg_main', bg_main)  # 讀主背景
            bg_panel = c.get('bg_panel', bg_panel)  # 讀板背景

        self.theme_accent = accent  # 賦值主色
        self.theme_border = border  # 賦值邊框
        self.theme_bg_panel = bg_panel  # 賦值背景

        # 📌 同步主視窗樣式，全面交由 skin.py 統一控管
        if self.parent_win:  # 有父視窗
            self.setStyleSheet(self.parent_win.styleSheet())  # 同步樣式



    def get_data(self):  # 回傳資料
        # 修正：回傳當前選中的 URL（如果有的話）
        selected_url = self.sources[self.selected_index]['url'] if 0 <= self.selected_index < len(self.sources) else None  # 取選取網址
        return self.sources, selected_url  # 回傳結果

    def refresh_list(self):  # 刷清列表
        self._updating = True   # 🔒 阻止 on_selection_changed 介入

        # 清空列表
        while self.list_widget.count() > 0:  # 還有項目
            item = self.list_widget.takeItem(0)  # 移出項目
            widget = self.list_widget.itemWidget(item)  # 取得組件
            if widget:  # 組件存在
                widget.deleteLater()  # 延遲銷毀
            del item  # 刪除物件
        self.list_widget.clear()  # 徹底清空

        filter_text = self.search_input.text().strip().lower()  # 搜尋關鍵
        accent = getattr(self, 'theme_accent', '#a855f7')  # 取得主色
        border = getattr(self, 'theme_border', '#581c87')  # 取得邊框
        bg_panel = getattr(self, 'theme_bg_panel', '#121520')  # 取得背景

        # 重建列表
        for idx, src in enumerate(self.sources):  # 遍歷來源
            name = src.get('name', '未命名')  # 取得名稱
            url = src.get('url', '')  # 取得網址
            is_local = url.lower().endswith(('m3u', 'm3u8', 'txt')) and not url.lower().startswith(('http://', 'https://'))  # 判定本地
            is_active = (idx == self.selected_index)   # 暫時標記

            if filter_text and (filter_text not in name.lower() and filter_text not in url.lower()):  # 過濾匹配
                continue  # 跳過非選

            card = M3U管理框架(
                name, url,
                is_local=is_local,
                is_active=is_active,
                accent=accent,
                border=border,
                bg_panel=bg_panel
            )  # 建卡片窗
            item = QListWidgetItem()  # 建列表項
            item.setSizeHint(QSize(460, 72))  # 設定尺寸
            item.setData(Qt.ItemDataRole.UserRole, src)  # 儲存資料
            self.list_widget.addItem(item)  # 加入項目
            self.list_widget.setItemWidget(item, card)  # 綁定卡片

        # ----- 設定當前選中項（直接處理，考慮過濾） -----
        if self.selected_index >= 0 and self.selected_index < len(self.sources):  # 有選中項
            target_src = self.sources[self.selected_index]  # 目標資料
            found = False  # 找到標誌
            for i in range(self.list_widget.count()):  # 遍歷項目
                item = self.list_widget.item(i)  # 取得項目
                src = item.data(Qt.ItemDataRole.UserRole)  # 取得資料
                if src is target_src or (src and src.get('url') == target_src.get('url')):  # 身份或網址吻合
                    self.list_widget.setCurrentItem(item)  # 選取該項
                    self.list_widget.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)  # 捲動視圖
                    found = True  # 設定標記
                    break  # 跳出迴圈
            if not found:  # 過濾沒中
                if self.list_widget.count() > 0:  # 列表非空
                    self.list_widget.setCurrentRow(0)  # 選第一項
                else:  # 列表無項
                    self.list_widget.clearSelection()  # 清除選取
        else:  # 無選中項
            self.list_widget.clearSelection()  # 清除選取

        # 🆕 統一更新所有卡片的 active 狀態（確保視覺與選中一致）
        current_item = self.list_widget.currentItem()  # 當前選項
        for i in range(self.list_widget.count()):  # 遍歷列表
            item = self.list_widget.item(i)  # 取列表項
            card = self.list_widget.itemWidget(item)  # 取卡片窗
            if card:  # 卡片存在
                card.set_active(item == current_item)  # 更新狀態

        self._updating = False   # 🔓 解鎖

    def on_selection_changed(self):  # 選項改變
        if self._updating:   # 如果正在 refresh，就乜都唔做
            return  # 解鎖結束
        selected_item = self.list_widget.currentItem()  # 當前項目
        if not selected_item:  # 項目無效
            return  # 結束執行
        src = selected_item.data(Qt.ItemDataRole.UserRole)  # 取得資料
        if not src:  # 資料無效
            return  # 結束執行
        # 用物件身份定位來源索引（重複的 name+url 也不會誤判）
        self.selected_index = self._index_of(src)  # 定位索引
        # 更新所有卡片的 active 狀態
        for i in range(self.list_widget.count()):  # 遍歷列表
            item = self.list_widget.item(i)  # 取得項目
            card = self.list_widget.itemWidget(item)  # 取得卡片
            if card:  # 卡片存在
                card.set_active(item == selected_item)  # 設定選取

    def add_file(self):  # 添加文件
        file_path, _ = QFileDialog.getOpenFileName(self, "選擇 M3U 播放列表檔", "", "M3U Files (*.m3u *.m3u8 *.txt);;All Files (*)")  # 選檔案窗
        if file_path:  # 選擇有效
            dlg = 編輯彈窗(name="本地播放列表", url=file_path, parent=self)  # 建編輯窗
            if dlg.exec() == QDialog.DialogCode.Accepted:  # 確認按鈕
                new_name, new_url, new_epg, new_logo = dlg.get_data()  # 讀取全部欄位
                name = new_name or "本地播放列表"  # 讀取名稱
                if new_url:  # 網址有效
                    self.sources.append({'name': name, 'url': new_url, 'epg': new_epg, 'logo': new_logo})  # 加入來源
                    self.selected_index = len(self.sources) - 1  # 切換選取
                    self.refresh_list()  # 刷新列表

    def add_url(self):  # 添加鏈接
        dlg = M3U添加網址彈窗(self)  # 建網址窗
        if dlg.exec() == QDialog.DialogCode.Accepted:  # 按下確認
            name = dlg.name_input.text().strip() or "網絡訂閱"  # 讀取名稱
            url = dlg.url_input.text().strip()  # 讀取網址
            epg = dlg.epg_input.text().strip()  # 讀取EPG
            logo = dlg.logo_input.text().strip()  # 讀取台徽
            if url:  # 網址有效
                self.sources.append({'name': name, 'url': url, 'epg': epg, 'logo': logo})  # 加入來源
                self.selected_index = len(self.sources) - 1  # 切換選取
                self.refresh_list()  # 刷新列表
                
    def add_xtream(self):  # 添加 Xtream
        dlg = M3U添加Xtream彈窗(self)  # 建碼視窗
        if dlg.exec() == QDialog.DialogCode.Accepted:  # 按下確認
            data = dlg.get_data()  # 取得資料
            if data:  # 資料有效
                self.sources.append(data)  # 加入來源
                self.selected_index = len(self.sources) - 1  # 切換選取
                self.refresh_list()  # 刷新列表

    def edit_source(self):  # 編輯來源
        selected_item = self.list_widget.currentItem()  # 取得選項
        if not selected_item:  # 選項空白
            return  # 結束執行
        src = selected_item.data(Qt.ItemDataRole.UserRole)  # 取得資料
        if not src:  # 資料空白
            return  # 結束執行
        # 找出在 sources 中的索引（身份定位，重複項不誤判）
        row = self._index_of(src)  # 取得行號
        if row == -1:  # 未能找到
            return  # 結束執行

        xtream_info = parse_xtream_url(src.get('url', ''))  # 解析Xtream

        if xtream_info:  # 是Xtream
            dlg = M3U添加Xtream彈窗(self)  # 建編輯窗
            dlg.name_input.setText(src.get('name', ''))  # 填入名稱
            dlg.server_input.setText(xtream_info['server'])  # 填入伺服
            dlg.user_input.setText(xtream_info['username'])  # 填入帳號
            dlg.pass_input.setText(xtream_info['password'])  # 填入密碼
            dlg.epg_input.setText(src.get('epg', ''))  # 填入EPG
            dlg.logo_input.setText(src.get('logo', ''))  # 填入台徽
            if dlg.exec() == QDialog.DialogCode.Accepted:  # 按下確認
                new_data = dlg.get_data()  # 取得新值
                self.sources[row].update(new_data)  # 更新來源
                self.selected_index = row   # 保持同一行
                self.refresh_list()  # 刷新列表
        else:  # 普通來源
            # 普通編輯
            dlg = 編輯彈窗(
                name=src.get('name', ''),
                url=src.get('url', ''),
                epg_url=src.get('epg', ''),
                logo_url=src.get('logo', ''),
                parent=self
            )  # 建編輯窗
            if dlg.exec() == QDialog.DialogCode.Accepted:  # 按下確認
                new_name, new_url, new_epg, new_logo = dlg.get_data()  # 取得新值
                self.sources[row]['name'] = new_name or "未命名訂閱"  # 更新名稱
                self.sources[row]['url'] = new_url  # 更新網址
                self.sources[row]['epg'] = new_epg  # 更新EPG
                self.sources[row]['logo'] = new_logo  # 更新台徽
                self.selected_index = row  # 保留選取
                self.refresh_list()  # 刷新列表

    def delete_source(self):  # 刪除來源
        selected_item = self.list_widget.currentItem()  # 取得選項
        if not selected_item:  # 選項空白
            return  # 結束執行
        src = selected_item.data(Qt.ItemDataRole.UserRole)  # 取得資料
        if not src:  # 資料空白
            return  # 結束執行
        # 找出在 sources 中的索引（身份定位，重複項不誤判）
        row = self._index_of(src)  # 取得行號
        if row == -1:  # 未能找到
            return  # 結束執行
        self.sources.pop(row)  # 移除來源
        # 調整 selected_index
        if self.selected_index == row:  # 選中刪除列
            self.selected_index = min(row, len(self.sources) - 1) if self.sources else -1  # 移至鄰近
        elif self.selected_index > row:  # 刪除前列
            self.selected_index -= 1  # 索引減一
        self.refresh_list()  # 刷新列表

class M3U管理框架(QFrame):  # 卡片框架
    def __init__(self, name, url, is_local=False, is_active=False, parent=None, accent="#a855f7", border="#581c87", bg_panel="#121520"):  # 初始化
        super().__init__(parent)  # 呼叫父類
        self.is_local = is_local  # 是否本地
        self.accent = accent  # 強調顏色
        self.border_color = border  # 邊框顏色
        self.bg_panel = bg_panel  # 背景顏色
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # 啟用背景
        self.setObjectName("m3u_item_frame")  # 元件命名
        self.setFixedHeight(64)  # 固定高度
        # 🎯 設置最小寬度，當父容器太窄時觸發橫向 Scrollbar
        self.setMinimumWidth(450)  # 最小寬度
        
        layout = QHBoxLayout(self)  # 水平佈局
        layout.setContentsMargins(14, 6, 14, 6)  # 邊距設定
        layout.setSpacing(10)  # 間距設定

        info_layout = QVBoxLayout()  # 資訊佈局
        info_layout.setSpacing(2)  # 間距設定
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # 垂直置中

        self.title_lbl = QLabel(name)  # 標題標籤
        self.title_lbl.setObjectName("m3u_item_title")  # 標題命名

        # 🎯 網址 Label 設置：自動截斷 + ToolTip 懸停查看完整 URL
        self.url_lbl = QLabel(url)  # 網址標籤
        self.url_lbl.setObjectName("m3u_item_url")  # 網址命名
        self.url_lbl.setToolTip(url)  # 提示網址

        info_layout.addWidget(self.title_lbl)  # 加入標題
        info_layout.addWidget(self.url_lbl)  # 加入網址
        layout.addLayout(info_layout, stretch=1)  # 加入資訊

        badge_layout = QHBoxLayout()  # 標籤佈局
        badge_layout.setSpacing(6)  # 間距設定
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # 垂直置中

        badge_type = "本地" if is_local else "URL"  # 類型標籤
        self.badge_lbl = QLabel(badge_type)  # 類別標籤
        self.badge_lbl.setObjectName("m3u_item_badge")  # 類別命名
        
        badge_layout.addWidget(self.badge_lbl)  # 加入類別

        self.star_lbl = QLabel("⭐")  # 星號標籤
        self.star_lbl.setObjectName("m3u_item_star")  # 星號命名
        badge_layout.addWidget(self.star_lbl)  # 加入星號

        layout.addLayout(badge_layout)  # 加入標籤
        self.set_active(is_active)  # 設定啟用

    def set_active(self, is_active):  # 設定作用
        self.is_active = is_active  # 儲存狀態
        self.star_lbl.setVisible(is_active)  # 顯示星星
        
        # 📌 配合 skin.py 的屬性選擇器驅動，利用動態屬性控制外觀狀態
        self.setProperty("active", "true" if is_active else "false")  # 設定屬性
        self.style().unpolish(self)  # 取消樣式
        self.style().polish(self)  # 刷新樣式
        self.update()  # 重新繪製

class M3U操作彈窗(QDialog):  # 操作對話
    def __init__(self, title, parent=None):  # 初始化
        super().__init__(parent)  # 呼叫父類
        self.setWindowTitle(title)  # 設定標題
        self.setFixedWidth(400)  # 固定寬度

class M3U添加網址彈窗(M3U操作彈窗):  # 加網彈窗
    def __init__(self, parent=None):  # 初始化
        super().__init__("添加網絡鏈接", parent)  # 呼叫父類
        layout = QVBoxLayout(self)  # 垂直佈局
        layout.setContentsMargins(20, 20, 20, 20)  # 邊距設定
        layout.setSpacing(12)  # 間距設定

        layout.addWidget(QLabel("訂閱名稱"))  # 名稱標籤
        self.name_input = QLineEdit()  # 名稱輸入
        self.name_input.setPlaceholderText("請輸入訂閱名稱 (如：IPTV / Live)")  # 提示文字
        layout.addWidget(self.name_input)  # 加入輸入

        layout.addWidget(QLabel("M3U 網址"))  # 網址標籤
        self.url_input = QLineEdit()  # 網址輸入
        self.url_input.setPlaceholderText("https://abc.de.fg/live.m3u")  # 提示文字
        layout.addWidget(self.url_input)  # 加入輸入

        # 🎯 新增：EPG 網址輸入框
        layout.addWidget(QLabel("EPG 地址 (使用逗號合併多個 EPG):"))  # EPG標籤
        self.epg_input = QLineEdit()  # EPG輸入
        self.epg_input.setPlaceholderText("默認例子：https://live.fanmingming.cn/e.xml")  # 提示文字
        layout.addWidget(self.epg_input)  # 加入輸入
        
        # 🎯 新增：台徽推送/範本網址輸入框 (支援 {name} 與逗號分隔)
        layout.addWidget(QLabel("台徽推送範本 (使用逗號分隔多個，支援 {name} 自動匹配):"))  # 台徽標籤
        self.logo_input = QLineEdit()  # 台徽輸入
        self.logo_input.setPlaceholderText("默認例子：https://live.fanmingming.cn/tv/{name}.png") #提示
        layout.addWidget(self.logo_input)  # 加入輸入

        btn_layout = QHBoxLayout()  # 按鈕佈局
        btn_layout.addStretch()  # 填滿餘白
        ok_btn = QPushButton("確定"); ok_btn.setProperty("class", "confirm-btn")  # 確定按鈕
        cancel_btn = QPushButton("取消"); cancel_btn.setProperty("class", "cancel-btn")  # 取消按鈕
        ok_btn.clicked.connect(self.accept); cancel_btn.clicked.connect(self.reject)  # 事件綁定
        btn_layout.addWidget(ok_btn); btn_layout.addWidget(cancel_btn)  # 加入按鈕
        layout.addLayout(btn_layout)  # 加入佈局

class M3U添加Xtream彈窗(M3U操作彈窗):  # 加碼彈窗
    def __init__(self, parent=None):  # 初始化
        super().__init__("添加 Xtream 代碼", parent)  # 呼叫父類
        layout = QVBoxLayout(self)  # 垂直佈局
        layout.setContentsMargins(20, 20, 20, 20)  # 邊距設定
        layout.setSpacing(10)  # 間距設定

        layout.addWidget(QLabel("訂閱名稱"))  # 名稱標籤
        self.name_input = QLineEdit()  # 名稱輸入
        layout.addWidget(self.name_input)  # 加入輸入

        layout.addWidget(QLabel("服務器 URL"))  # 伺服標籤
        self.server_input = QLineEdit()  # 伺服輸入
        self.server_input.setPlaceholderText("http://example.com:8080")  # 提示文字
        layout.addWidget(self.server_input)  # 加入輸入

        layout.addWidget(QLabel("用戶名"))  # 帳號標籤
        self.user_input = QLineEdit()  # 帳號輸入
        layout.addWidget(self.user_input)  # 加入輸入

        layout.addWidget(QLabel("密碼"))  # 密碼標籤
        self.pass_input = QLineEdit()  # 密碼輸入
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)  # 遮罩密碼
        layout.addWidget(self.pass_input)  # 加入輸入

        # 🎯 EPG 網址（可逗號合併多個）
        layout.addWidget(QLabel("EPG 地址 (使用逗號合併多個 EPG):"))  # EPG標籤
        self.epg_input = QLineEdit()  # EPG輸入
        self.epg_input.setPlaceholderText("默認例子：https://live.fanmingming.cn/e.xml")  # 提示文字
        layout.addWidget(self.epg_input)  # 加入輸入

        # 🎯 台徽推送/範本網址（支援 {name} 與逗號分隔）
        layout.addWidget(QLabel("台徽推送範本 (使用逗號分隔多個，支援 {name} 自動匹配):"))  # 台徽標籤
        self.logo_input = QLineEdit()  # 台徽輸入
        self.logo_input.setPlaceholderText("默認例子：https://live.fanmingming.cn/tv/{name}.png")  # 提示文字
        layout.addWidget(self.logo_input)  # 加入輸入

        btn_layout = QHBoxLayout()  # 按鈕佈局
        btn_layout.addStretch()  # 填滿餘白
        ok_btn = QPushButton("確定"); ok_btn.setProperty("class", "confirm-btn")  # 確定按鈕
        cancel_btn = QPushButton("取消"); cancel_btn.setProperty("class", "cancel-btn")  # 取消按鈕
        ok_btn.clicked.connect(self.accept); cancel_btn.clicked.connect(self.reject)  # 事件綁定
        btn_layout.addWidget(ok_btn); btn_layout.addWidget(cancel_btn)  # 加入按鈕
        layout.addLayout(btn_layout)  # 加入佈局
        
    def get_data(self):  # 回傳資料
        name = self.name_input.text().strip() or "Xtream IPTV"  # 取得名稱
        srv = self.server_input.text().strip().rstrip('/')  # 取得伺服
        usr = self.user_input.text().strip()  # 取得帳號
        pwd = self.pass_input.text().strip()  # 取得密碼
        # 重建時重新做 URL 編碼，與 parse_xtream_url 的「解碼→編輯→再編碼」閉環一致
        generated_url = (  # 組成網址
            f"{srv}/get.php?username={quote(usr, safe='')}"
            f"&password={quote(pwd, safe='')}"
            f"&type=m3u_plus&output=ts"
        )  # 括號結尾
        return {  # 回傳字典
            'name': name,  # 訂閱名稱
            'url': generated_url,  # 播放網址
            'epg': self.epg_input.text().strip(),  # 節目網址
            'logo': self.logo_input.text().strip(),  # 台徽範本
        }  # 字典結尾

class 編輯彈窗(M3U操作彈窗):  # 編輯彈窗
    def __init__(self, name="", url="", epg_url="", logo_url="", parent=None):  # 初始化
        super().__init__("編輯訂閱網址", parent)  # 呼叫父類
        layout = QVBoxLayout(self)  # 垂直佈局
        layout.setContentsMargins(20, 20, 20, 20)  # 邊距設定
        layout.setSpacing(12)  # 間距設定

        layout.addWidget(QLabel("訂閱名稱"))  # 名稱標籤
        self.name_input = QLineEdit(name)  # 名稱輸入
        self.name_input.setPlaceholderText("例如：IPTV")  # 提示文字
        layout.addWidget(self.name_input)  # 加入輸入

        layout.addWidget(QLabel("訂閱網址 / 本地M3U文件路徑"))  # 網址標籤
        self.url_input = QLineEdit(url)  # 網址輸入
        self.url_input.setPlaceholderText("https://... 或本地 .m3u 路徑")  # 提示文字
        layout.addWidget(self.url_input)  # 加入輸入

        # 🎯 新增：EPG 網址編輯輸入框
        layout.addWidget(QLabel("EPG 地址 (使用逗號合併多個 EPG):"))  # EPG標籤
        self.epg_input = QLineEdit(epg_url)  # EPG輸入
        self.epg_input.setPlaceholderText("默認例子：https://live.fanmingming.cn/e.xml")  # 提示文字
        layout.addWidget(self.epg_input)  # 加入輸入
        
        # 🎯 新增：台徽推送/範本網址輸入框 (支援 {name} 與逗號分隔)
        layout.addWidget(QLabel("台徽推送範本 (使用逗號分隔多個，支援 {name} 自動匹配):"))  # 台徽標籤
        self.logo_input = QLineEdit()  # 台徽輸入
        self.logo_input.setPlaceholderText("默認例子：https://live.fanmingming.cn/tv/{name}.png") #提示
        self.logo_input.setText(logo_url)   # 填入台徽
        layout.addWidget(self.logo_input)  # 加入輸入

        btn_layout = QHBoxLayout()  # 按鈕佈局
        btn_layout.addStretch()  # 填滿餘白
        ok_btn = QPushButton("確定"); ok_btn.setProperty("class", "confirm-btn")  # 確定按鈕
        cancel_btn = QPushButton("取消"); cancel_btn.setProperty("class", "cancel-btn")  # 取消按鈕
        ok_btn.clicked.connect(self.accept); cancel_btn.clicked.connect(self.reject)  # 事件綁定
        btn_layout.addWidget(ok_btn); btn_layout.addWidget(cancel_btn)  # 加入按鈕
        layout.addLayout(btn_layout)  # 加入佈局

    def get_data(self):  # 回傳資料
        return (
            self.name_input.text().strip(),
            self.url_input.text().strip(),
            self.epg_input.text().strip(),
            self.logo_input.text().strip()
        )  # 回傳四元
# [代碼終點]