# [代碼起點]
from config import *  # 匯入配置

from skin import IconManager  # 匯入圖標
from epg_manager import channel_match_keys  # 頻道鍵值

class EPGPanelWidget(QWidget):  # 節目面板
    def __init__(self, main_win):  # 初始化
        super().__init__(main_win)  # 呼叫父類
        self.main_win = main_win  # 綁定主視
        self.setObjectName("epg_panel")  # 設定物件
        self.setMinimumWidth(340)  # 最小寬度
        self.setMaximumWidth(16777215)  # 最大寬度
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # 縮放策略

        self._init_ui()  # 建立介面

    def _init_ui(self):  # 介面方法
        """初始化右側 EPG 節目表面板 UI"""
        epg_layout = QVBoxLayout(self)  # 直排佈局
        epg_layout.setContentsMargins(12, 12, 12, 12)  # 外框邊距
        epg_layout.setSpacing(8)  # 元件間距

        epg_title_layout = QHBoxLayout()  # 橫排佈局
        epg_title_layout.setContentsMargins(0, 0, 0, 0)  # 標頭邊距
        epg_title_layout.setSpacing(6)  # 標頭間距

        epg_icon_lbl = QLabel()  # 圖標標籤
        epg_icon = IconManager.get_icon("epg", color="#ffffff", size=18)  # 載入圖標
        epg_icon_lbl.setPixmap(epg_icon.pixmap(18, 18))  # 設置圖標

        epg_title_txt = QLabel("節目表 (EPG)")  # 標題文字
        epg_title_txt.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")  # 文字樣式

        epg_title_layout.addWidget(epg_icon_lbl)  # 加入圖標
        epg_title_layout.addWidget(epg_title_txt)  # 加入文字
        epg_title_layout.addStretch()  # 彈簧推開

        epg_layout.addLayout(epg_title_layout)  # 加入標題

        self.epg_list_widget = QListWidget()  # 節目列表
        self.epg_list_widget.setObjectName("epg_list_widget")  # 物件命名

        self.programme_detail = QLabel("選擇節目以查看簡介")  # 詳情標籤
        self.programme_detail.setObjectName("programme_detail")  # 物件命名
        self.programme_detail.setWordWrap(True)  # 自動換行
        self.programme_detail.setTextFormat(Qt.TextFormat.PlainText)  # 純文字格式
        self.programme_detail.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)  # 靠左對齊
        self.programme_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)  # 可選取複製
        self.programme_detail.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)  # 可隨內容長高
        self.programme_detail.setStyleSheet(
            "color: #d7d7e0; background: rgba(255,255,255,0.05); "
            "border: 1px solid rgba(255,255,255,0.10); border-radius: 7px; padding: 8px;"
        )  # 詳情樣式

        self.detail_scroll = QScrollArea()  # 詳情捲動區
        self.detail_scroll.setObjectName("epg_detail_scroll")  # 物件命名
        self.detail_scroll.setWidgetResizable(True)  # 內容隨寬度自動換行
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)  # 無外框
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 不顯示橫向條
        self.detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 需要時才出現直向條
        self.detail_scroll.setFixedHeight(120)  # 固定高度（維持舊版觀感）
        self.detail_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; } "
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )  # 透明底，讓簡介自身的框線與底色顯示
        self.detail_scroll.setWidget(self.programme_detail)  # 放入詳情

        epg_layout.addWidget(self.epg_list_widget, 1)  # 加入節目列表
        epg_layout.addWidget(self.detail_scroll)  # 加入詳情（固定高度＋右側滾動）

        self.epg_list_widget.currentItemChanged.connect(self._show_programme_details)  # 點擊連線

        # 保持與主視窗相容之屬性綁定
        self.main_win.epg_list_widget = self.epg_list_widget  # 綁定主視

    def _show_programme_details(self, item, _previous=None):  # 顯示詳情
        """只讀取已解析的 EPG metadata，不在選取節目時產生網路請求。"""
        programme = item.data(Qt.ItemDataRole.UserRole) if item else None  # 取得資料
        if not isinstance(programme, dict):  # 非字典檔
            self.programme_detail.setText("選擇節目以查看簡介")  # 預設提示
            return  # 結束執行

        lines = []  # 內文陣列
        title = str(programme.get('title', '') or '').strip()  # 節目標題
        if title:  # 有標題
            lines.append(title)  # 先顯示標題（部分 EPG 只提供標題）
        time_text = self._format_time_range(programme)  # 時間範圍
        if time_text:  # 有時間
            lines.append(time_text)  # 加入時間
        subtitle = str(programme.get('subtitle', '') or '').strip()  # 副標文字
        if subtitle:  # 存在副標
            lines.append(subtitle)  # 加入副標
        episode_num = str(programme.get('episode_num', '') or '').strip()  # 集數文字
        category = str(programme.get('category', '') or '').strip()  # 分類文字
        tags = [tag for tag in (episode_num, category) if tag]  # 組合標籤
        if tags:  # 存在標籤
            lines.append(" · ".join(tags))  # 接合標籤
        description = str(programme.get('desc', '') or '').strip()  # 節目簡介
        if description:  # 存在簡介
            lines.append(description)  # 加入簡介
        elif not subtitle:  # 連副標都沒有
            lines.append("此 EPG 來源沒有提供節目簡介")  # 提示缺簡介
        self.programme_detail.setText("\n".join(lines) if lines else "此 EPG 來源沒有提供節目簡介")  # 顯示文字
        try:  # 重設捲動位置
            self.detail_scroll.verticalScrollBar().setValue(0)  # 回到最頂
        except Exception:  # 忽略例外
            pass  # 不影響顯示

    def _format_time_range(self, programme):  # 時間範圍
        """把 XMLTV start/stop 轉成 HH:MM - HH:MM（解析失敗回傳空字）"""
        try:  # 嘗試轉換
            start = str(programme.get('start', '') or '').split()[0][:14].ljust(14, '0')  # 開始時間
            stop = str(programme.get('stop', '') or '').split()[0][:14].ljust(14, '0')  # 結束時間
            start_dt = datetime.strptime(start, "%Y%m%d%H%M%S")  # 開始物件
            stop_dt = datetime.strptime(stop, "%Y%m%d%H%M%S")  # 結束物件
            return f"{start_dt.strftime('%H:%M')} - {stop_dt.strftime('%H:%M')}"  # 回傳格式
        except Exception:  # 解析失敗
            return ''  # 回傳空字

    def toggle_panel(self):  # 切換開關
        """切換右側 EPG 節目表顯示狀態"""
        is_opening = not self.isVisible()  # 開關狀態
        self.setVisible(is_opening)  # 設置顯示

        QTimer.singleShot(20, self.main_win._auto_adjust_bottom_controls)  # 微調底欄
        if self.main_win.isFullScreen():  # 全屏時重算分欄
            QTimer.singleShot(0, self.main_win._fs_resize_splitter)  # 延遲套用

        if is_opening:  # 面板開啟
            raw_name = self.main_win.current_channel_name  # 原始名稱
            if not raw_name:  # 名稱空白
                idx = self.main_win.active_player_index  # 當前播放
                if 0 <= idx < len(self.main_win.video_widgets):  # 索引有效
                    w = self.main_win.video_widgets[idx]  # 取得視窗
                    raw_name = getattr(w, 'channel_name', '') or getattr(w, 'channel_info', {}).get('name', '')  # 抓頻道名

            clean_name = re.sub(r'^\d+\.\s*', '', raw_name)  # 去前數字
            clean_name = re.sub(r'\s+\[(?!HD|SD|4K|FHD).*?\]$', '', clean_name, flags=re.IGNORECASE).strip()  # 去後雜訊
            if not clean_name:  # 清洗空白
                clean_name = raw_name.strip()  # 整理原始

            print(f"📺 [DEBUG] 打開 EPG 面板！目標頻道名稱: '{clean_name}'")  # 除錯訊息

            if clean_name:  # 名稱存在
                self.main_win.current_channel_name = clean_name  # 更新主視

            self.update_epg_content(clean_name)  # 刷新節目

    def update_epg_content(self, channel_name=None):  # 更新列表
        """更新 EPG 節目表內容（回歸內存字典模式）"""
        if channel_name:  # 傳入名稱
            self.main_win.current_channel_name = channel_name  # 更新名稱

        if self.epg_list_widget is None:  # 無列表項
            return  # 結束執行

        self.epg_list_widget.blockSignals(True)  # 阻斷訊號
        self.epg_list_widget.clear()  # 清空列表
        current_ch = self.main_win.current_channel_name  # 當前頻道
        if not current_ch or "請點擊左側頻道" in current_ch:  # 未選頻道
            self.epg_list_widget.addItem("⚠️ 請先選擇並播放頻道")  # 提示選擇
            self.epg_list_widget.blockSignals(False)  # 恢復訊號
            self._show_programme_details(None)  # 清空詳情
            return  # 結束執行

        # ✅ 重點：直接讀取內存字典！
        epg_db_data = self.main_win.epg_lookup or self.main_win.epg_data or self.main_win.epg_cache  # 讀取快取
        if not epg_db_data:  # 快取為空
            self.epg_list_widget.addItem("⚠️ EPG 資料庫為空，請確定已載入 EPG 網址")  # 提示空庫
            self.epg_list_widget.blockSignals(False)  # 恢復訊號
            self._show_programme_details(None)  # 清空詳情
            return  # 結束執行

        # 構建匹配 Key（繁簡/符號歸一化，避免「龍華經典 vs 龙华经典」這類漏配）
        raw_name = current_ch.replace("📺", "").replace("⭐", "").replace("🕒", "").strip()  # 去除圖示

        ch_obj = self.main_win.current_channel_obj or {}  # 頻道物件
        values = [raw_name]  # 待比對欄位
        if isinstance(ch_obj, dict):  # 為字典型
            values.append(ch_obj.get('tvg_id', ''))  # 加電視ID
            values.append(ch_obj.get('tvg_name', ''))  # 加電視名
        keys_to_check = channel_match_keys(*values)  # 產生完整鍵集（含繁簡歸一化）

        matched_items = []  # 匹配結果
        for k in keys_to_check:  # 尋找匹配
            if k in epg_db_data:  # 鍵值存在
                matched_items = epg_db_data[k]  # 取得節目
                break  # 跳出迴圈

        if not matched_items:  # 無匹配項
            self.epg_list_widget.addItem(f"⚠️ 頻道: {raw_name}\n未找到 EPG 節目單")  # 提示無單
            self.epg_list_widget.blockSignals(False)  # 恢復訊號
            self._show_programme_details(None)  # 清空詳情
            return  # 結束執行

        # 去重並顯示
        seen_progs = set()  # 已見節目
        unique_progs = []  # 唯一節目
        for p in matched_items:  # 遍歷節目
            prog_tuple = (p.get('start'), p.get('stop'), p.get('title'))  # 節目特徵
            if prog_tuple not in seen_progs:  # 未曾出現
                seen_progs.add(prog_tuple)  # 記錄特徵
                unique_progs.append(p)  # 加入陣列

        now = datetime.now()  # 當前時間
        for prog in unique_progs:  # 顯示節目
            start_str = prog.get('start', '')  # 開始時間
            stop_str = prog.get('stop', '')  # 結束時間
            time_fmt = "--:--"  # 時間字串
            is_current = False  # 當前播中
            try:  # 捕捉例外
                s_raw = start_str.split()[0][:14]  # 切開始時
                e_raw = stop_str.split()[0][:14]  # 切結束時
                if len(s_raw) >= 12:  # 長度足夠
                    st = datetime.strptime(s_raw.ljust(14, '0'), "%Y%m%d%H%M%S")  # 開始物件
                    time_fmt = st.strftime("%H:%M")  # 格式時間
                    if len(e_raw) >= 12:  # 長度足夠
                        et = datetime.strptime(e_raw.ljust(14, '0'), "%Y%m%d%H%M%S")  # 結束物件
                        if st <= now <= et:  # 正在播放
                            is_current = True  # 標記當前
            except Exception:  # 解析失敗
                pass  # 忽略錯誤

            prefix = "▶ " if is_current else "   "  # 狀態前綴
            item_text = f"{prefix}[{time_fmt}]  {prog.get('title', '未知節目')}"  # 組合文字
            list_item = QListWidgetItem(item_text)  # 建立列表
            list_item.setData(Qt.ItemDataRole.UserRole, prog)  # 綁定數據
            if is_current:  # 當前節目
                list_item.setForeground(QColor("#00f2fe"))  # 青色高亮
                self.epg_list_widget.addItem(list_item)  # 加入列表
                self.epg_list_widget.setCurrentItem(list_item)  # 設為當前

                # 🎯 終極修正：鎖定「行索引」，唔好鎖死物件！
                target_row = self.epg_list_widget.row(list_item)  # 取得行號
                QTimer.singleShot(50, lambda r=target_row: self.epg_list_widget.scrollToItem(
                    self.epg_list_widget.item(r), QAbstractItemView.ScrollHint.PositionAtCenter
                ))  # 捲動中央
            else:  # 非當前項
                self.epg_list_widget.addItem(list_item)  # 加入列表

        self.epg_list_widget.blockSignals(False)  # 恢復訊號
        self._show_programme_details(self.epg_list_widget.currentItem())  # 更新詳情
# [代碼終點]
