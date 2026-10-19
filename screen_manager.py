# screen_manager.py

from config import *  # 載入設定

from widgets import RoundedMenu  # 載入選單

class ScreenManager(QObject):  # 螢幕管理類
    def __init__(self, main_window):  # 初始化器
        super().__init__(main_window)  # 父類初始化
        self.win = main_window  # 綁定主視窗
        self.current_menu = None  # 記目前選單
        # 相容舊介面
        self.win._event_filter_install_for_widgets = self.install_event_filters  # 綁定過濾器

    def install_event_filters(self):  # 安裝過濾器
        """🎯 自動為所有分屏框架與播放組件安裝事件過濾器"""  # 功能說明
        frames = self.win.video_frames  # 取得框架列
        widgets = self.win.video_widgets  # 取得播放器

        for frame in frames:  # 跑框架清單
            frame.removeEventFilter(self)  # 移除舊過濾
            frame.installEventFilter(self)  # 裝新過濾器

        for widget in widgets:  # 跑播放器列
            widget.removeEventFilter(self)  # 移除舊過濾
            widget.installEventFilter(self)  # 裝新過濾器

    def eventFilter(self, watched, event):  # 事件過濾器
        """🎯 攔截 4 個屏幕的滑鼠點擊事件，實現焦點切換與右鍵選單"""  # 功能說明
        if event.type() == QEvent.Type.MouseButtonPress:  # 攔截點擊檔
            widgets = getattr(self.win, 'video_widgets', [])  # 拿播放器列
            frames = getattr(self.win, 'video_frames', [])  # 拿框架清單

            target_idx = -1  # 預設未命中
            # 比對目標屏
            for i in range(max(len(widgets), len(frames))):  # 跑螢幕數量
                w = widgets[i] if i < len(widgets) else None  # 拿當前播放
                f = frames[i] if i < len(frames) else None  # 拿當前框架

                if watched == w or watched == f:  # 直接點中屏
                    target_idx = i  # 設定屏編號
                    break  # 跳出比對圈
                if w and w.isAncestorOf(watched):  # 點中播放子
                    target_idx = i  # 設定屏編號
                    break  # 跳出比對圈
                if f and hasattr(f, 'isAncestorOf') and f.isAncestorOf(watched):  # 點中框架子
                    target_idx = i  # 設定屏編號
                    break  # 跳出比對圈

            if target_idx != -1:  # 有命中螢幕
                # 切換焦點屏
                if event.button() == Qt.MouseButton.LeftButton:  # 按滑鼠左鍵
                    if self.win.active_player_index != target_idx:  # 焦點有變更
                        self.win.active_player_index = target_idx  # 設新焦點屏
                        self.update_screen_borders()  # 畫新邊框線
                        self._sync_audio_focus()  # 同步聲音屏

                # 彈出選單列
                elif event.button() == Qt.MouseButton.RightButton:  # 按滑鼠右鍵
                    w = widgets[target_idx] if target_idx < len(widgets) else frames[target_idx]  # 拿目標物件
                    pos = event.pos() if hasattr(event, 'pos') else event.position().toPoint()  # 拿點擊位置
                    self._show_context_menu_for_widget(pos, w)  # 顯右鍵選單

        return super().eventFilter(watched, event)  # 交回父過濾

    def set_screen_layout(self, count):  # 排分屏佈局
        """設定分屏數量 (1~4屏) 並重新排版與動態釋放記憶體"""  # 功能說明
        # 記憶體策略
        is_multi = (count > 1)  # 是否多螢幕
        limit_mb = 15 if is_multi else 30  # 快取上限值
        
        for w in self.win.video_widgets:  # 跑所有播放
            w.is_multi_mode = is_multi  # 標註多屏態
            if w._ctx:  # 有核心實體
                w._set_property_string("demuxer-max-bytes", f"{limit_mb}M")  # 執行時要用 property

        self.win.setUpdatesEnabled(False)  # 關畫面更新
        try:  # 嘗試佈局
            # 清理非活屏
            for i in range(len(self.win.video_widgets)):  # 跑播放器列
                if i >= count:  # 超出顯示數
                    widget = self.win.video_widgets[i]  # 拿隱藏播放
                    if not getattr(widget, "has_media", False) and not getattr(widget, "_current_url", ""):  # 本來就空白
                        continue  # 不用重複清理
                    if hasattr(widget, "clear_media"):  # 新介面：完全清空
                        widget.clear_media()  # 停止並清網址/名稱
                    else:  # 舊介面
                        widget.stop()  # 停止播放流
                        widget.has_media = False  # 設無媒體檔
                        widget.update()  # 刷新畫面顯

            while self.win.grid_layout.count():  # 版面有元件
                item = self.win.grid_layout.takeAt(0)  # 取出舊元件
                if item and item.widget():  # 確有視窗件
                    item.widget().hide()  # 隱藏該視窗

            positions = {  # 分屏座標對
                1: [(0, 0, 2, 2)],  # 單屏全螢幕
                2: [(0, 0, 2, 1), (0, 1, 2, 1)],  # 雙屏左右
                3: [(0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)],  # 三屏1:2
                4: [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)]  # 四屏田字
            }  # 對應表結尾

            layout_map = positions.get(count, positions[1])  # 拿位置清單
            for idx, pos in enumerate(layout_map):  # 跑座標資料
                if idx < len(self.win.video_frames):  # 未超出框架
                    frame = self.win.video_frames[idx]  # 拿對應框架
                    self.win.grid_layout.addWidget(frame, pos[0], pos[1], pos[2], pos[3])  # 入格子排版
                    frame.show()  # 顯示該框架
        finally:  # 必定執行
            self.win.setUpdatesEnabled(True)  # 開畫面更新

        if self.win.active_player_index >= count:  # 焦點已越界
            self.win.active_player_index = 0  # 歸零焦點屏

        self.update_screen_borders()  # 畫邊框顏色
        self._sync_audio_focus()  # 開對應聲音
        self.install_event_filters()  # 重新裝過濾

    def update_screen_borders(self):  # 刷新邊框線
        """🎯 更新分屏邊框高亮樣式與頂欄/頻道清單連動"""  # 功能說明
        visible_frames = [f for f in self.win.video_frames if f.isVisible()]  # 拿可見框架
        visible_count = len(visible_frames)  # 算顯示數量
        accent_color = self.win.current_theme_accent  # 拿主題色彩

        for i, frame in enumerate(self.win.video_frames):  # 跑全部框架
            if frame.isVisible():  # 框架可見時
                if visible_count <= 1:  # 只有一個屏
                    frame.layout().setContentsMargins(0, 0, 0, 0)  # 邊界歸零值
                    frame.setStyleSheet("QFrame { background-color: #000000; border: none; }")  # 無邊框樣式
                else:  # 有多個分屏
                    if i == self.win.active_player_index:  # 是焦點螢幕
                        frame.layout().setContentsMargins(2, 2, 2, 2)  # 設邊界寬度
                        frame.setStyleSheet(f"QFrame {{ background-color: {accent_color}; border: none; }}")  # 畫焦點邊框
                    else:  # 非焦點螢幕
                        dim_border_color = "#2a2a38"  # 暗色邊框值
                        frame.layout().setContentsMargins(2, 2, 2, 2)  # 設邊界寬度
                        frame.setStyleSheet(f"QFrame {{ background-color: {dim_border_color}; border: none; }}")  # 畫預設邊框

        idx = self.win.active_player_index  # 拿焦點索引
        clist = getattr(self.win, 'channel_list', None)  # 拿頻道清單

        if 0 <= idx < len(self.win.video_widgets):  # 索引有效時
            w = self.win.video_widgets[idx]  # 拿焦點播放

            ch_info = getattr(w, 'channel_info', None) or {}  # 拿頻道資訊
            ch_url = getattr(w, 'channel_url', None) or ch_info.get('url', '')  # 拿播放網址
            ch_name = getattr(w, 'channel_name', None) or ch_info.get('name', '')  # 拿頻道名稱

            if not ch_url or not ch_name:  # 缺網址名稱
                ch_obj = getattr(w, 'ch', None) or getattr(w, 'ch_data', None) or getattr(w, 'channel_data', None) or getattr(w, 'channel', None)  # 嘗試拿物件
                if isinstance(ch_obj, dict):  # 確定是字典
                    ch_url = ch_url or ch_obj.get('url', '')  # 補網址資料
                    ch_name = ch_name or ch_obj.get('name', '')  # 補名稱資料

            clean_name = ch_name.strip() if ch_name else ""  # 清去頭尾空
            has_media = getattr(w, 'has_media', False) or bool(ch_url or clean_name)  # 判斷有媒體

            # 更新標題列
            if hasattr(self.win, 'update_header_title'):  # 視窗有更新
                self.win.update_header_title(channel_name=clean_name)  # 刷頂欄標題

            if clist and clist.isVisible():  # 清單存在顯
                matched_item = None  # 預設無對應
                if has_media and (ch_url or clean_name):  # 確有頻道檔
                    for row in range(clist.count()):  # 跑清單列項目
                        item = clist.item(row)  # 拿行列物件
                        item_url = item.data(Qt.ItemDataRole.UserRole) or ''  # 拿綁定網址
                        item_ch = item.data(Qt.ItemDataRole.UserRole + 1) or {}  # 拿綁定資訊
                        item_name = item_ch.get('name', '') if isinstance(item_ch, dict) else ''  # 拿綁定名稱
                        clean_item_name = item_name.strip()  # 淨化頻道名

                        if ch_url and item_url == ch_url:  # 網址完全對
                            matched_item = item  # 找到對應列
                            break  # 跳出搜尋圈
                        elif clean_name and (clean_name == clean_item_name or clean_name in item.text()):  # 名稱完全對
                            matched_item = item  # 找到對應列
                            break  # 跳出搜尋圈

                clist.blockSignals(True)  # 暫停訊號發
                if matched_item:  # 有找到列項
                    clist.setCurrentItem(matched_item)  # 選取該項目
                    matched_item.setSelected(True)  # 設選取狀態
                    clist.scrollToItem(matched_item)  # 滾動至該列
                else:  # 沒有對應項
                    clist.clearSelection()  # 清除選取列
                    clist.setCurrentItem(None)  # 取消選取項
                clist.blockSignals(False)  # 恢復訊號發

    def _sync_audio_focus(self):  # 同步靜音態
        """🎯 B5終極修復：採用標準 Mute 開關，點邊個屏邊個有聲，其他全部靜音，並同步控制欄"""  # 功能說明
        if not self.win.video_widgets:  # 無播放組件
            return  # 結束不處理

        # 選中屏幕號
        target_idx = self.win.active_player_index  # 拿焦點索引

        # 防止索引錯
        if target_idx >= len(self.win.video_widgets):  # 索引超界線
            target_idx = 0  # 重設為零屏

        # 設定靜音狀態
        for idx, widget in enumerate(self.win.video_widgets):  # 跑所有播放
            try:  # 嘗試切靜音
                widget.set_mute(idx != target_idx)  # 非焦點靜音
            except Exception:  # 抓切換例外
                pass  # 忽略此錯誤

        # 刷新按鈕圖
        # 刷新控制列
        if hasattr(self.win, 'sync_controls_ui'):  # 視窗有同步
            self.win.sync_controls_ui()  # 同步控制欄
            
    def _show_context_menu_for_widget(self, pos, widget):  # 彈右鍵選單
        # 關閉舊選單
        if self.current_menu is not None:  # 已開有選單
            try:  # 嘗試關選單
                self.current_menu.close()  # 關閉舊選單
                self.current_menu.deleteLater()  # 釋放舊記憶
            except:  # 抓關閉例外
                pass  # 忽略該錯誤
            self.current_menu = None  # 清空選單變

        # 奪回視窗焦點
        main_window = self.win  # 拿主視窗件
        user32 = ctypes.windll.user32  # 載 WIN API
        hwnd = int(main_window.winId())  # 拿視窗控制
        user32.SetForegroundWindow(hwnd)  # 設最前焦點
        user32.SetFocus(hwnd)  # 設系統焦點
        QCoreApplication.processEvents()  # 刷事件隊列

        # 建立選單列
        menu = RoundedMenu(self.win)  # 建圓角選單
        self.current_menu = menu  # 記目前選單

        widgets = self.win.video_widgets or self.win.video_frames  # 拿所有螢幕
        idx = widgets.index(widget) if widget in widgets else 0  # 算螢幕編號

        # 封裝處理函
        def make_handler(func):  # 建立處理器
            def handler():  # 實際執行函
                # 關閉選單
                if self.current_menu is not None:  # 有開啟選單
                    self.current_menu.close()  # 關閉該選單
                    self.current_menu.deleteLater()  # 刪選單物件
                    self.current_menu = None  # 變數歸空值
                # 執行動作
                func()  # 執行目標函
            return handler  # 回傳處理器

        # 播放統計列
        action_stats = QAction("📊 播放統計資訊", self.win)  # 建動作項目
        def stats_func():  # 統計功能函
            if hasattr(widget, 'toggle_stats'):  # 元件有統計
                widget.toggle_stats()  # 切換顯示列
            elif hasattr(widget, 'mpv') and hasattr(widget.mpv, 'toggle_stats'):  # MPV有統計
                widget.mpv.toggle_stats()  # 切換統計列
        action_stats.triggered.connect(make_handler(stats_func))  # 點擊連功能
        menu.addAction(action_stats)  # 加入選單列
        
        menu.addSeparator()  # 加入分隔線

        # 複製網址列
        action_copy = QAction("🔗 複製當前串流 URL", self.win)  # 建複製項目
        def copy_func():  # 複製功能函
            url = getattr(widget, '_current_url', '')  # 取當前網址
            if not url and hasattr(widget, 'mpv'):  # 試從MPV拿
                url = getattr(widget.mpv, '_current_url', '')  # 拿 MPV 網址
            if url:  # 有網址內容
                QApplication.clipboard().setText(str(url))  # 寫剪貼簿內
        action_copy.triggered.connect(make_handler(copy_func))  # 點擊連功能
        menu.addAction(action_copy)  # 加入選單列

        menu.addSeparator()  # 加入分隔線
        
        # 貼上播放列
        action_paste = QAction("📋 貼上並播放剪貼簿網址", self.win)  # 建貼上項目
        def paste_func():  # 貼上功能函
            text = QApplication.clipboard().text().strip()  # 拿剪貼文字
            if text.startswith("http://") or text.startswith("https://"):  # 是合法網址
                self.win.drop_mgr.process_url(text)  # 交拖放處理
        action_paste.triggered.connect(make_handler(paste_func))  # 點擊連功能
        menu.addAction(action_paste)  # 加入選單列
        
        menu.addSeparator()  # 加入分隔線

        # 關當前分屏
        action_close_cur = QAction(f"❌ 關閉/切斷第 {idx + 1} 屏", self.win)  # 建關單屏項
        def close_cur_func():  # 關單屏功能
            self.win._close_single_widget(widget)  # 關閉該分屏
        action_close_cur.triggered.connect(make_handler(close_cur_func))  # 點擊連功能
        menu.addAction(action_close_cur)  # 加入選單列
        
        menu.addSeparator()  # 加入分隔線

        # 關其他分屏
        action_close_others = QAction("🧹 關閉其他所有分屏", self.win)  # 建關他屏項
        def close_others_func():  # 關他屏功能
            for w in list(widgets):  # 跑所有分屏
                if w != widget:  # 非當前分屏
                    self.win._close_single_widget(w)  # 關閉該分屏
        action_close_others.triggered.connect(make_handler(close_others_func))  # 點擊連功能
        menu.addAction(action_close_others)  # 加入選單列

        # 彈出視窗選
        global_pos = widget.mapToGlobal(pos)  # 轉全域座標
        menu.setFocus()  # 設選單焦點
        menu.popup(global_pos)  # 彈出選單列

        # 隱藏時清理
        def on_menu_hide():  # 選單隱藏函
            if self.current_menu == menu:  # 是目前選單
                self.current_menu = None  # 清除舊指標
        menu.aboutToHide.connect(on_menu_hide)  # 綁隱藏事件