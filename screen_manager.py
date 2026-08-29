# screen_manager.py

from config import *

from widgets import RoundedMenu

class ScreenManager(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.win = main_window
        self.current_menu = None   # <--- 新增呢行
        # 綁定相容接口，防止 main_window 呼叫舊方法時報錯
        self.win._event_filter_install_for_widgets = self.install_event_filters

    def install_event_filters(self):
        """🎯 自動為所有分屏框架與播放組件安裝事件過濾器"""
        frames = self.win.video_frames
        widgets = self.win.video_widgets

        for frame in frames:
            frame.removeEventFilter(self)
            frame.installEventFilter(self)

        for widget in widgets:
            widget.removeEventFilter(self)
            widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        """🎯 攔截 4 個屏幕的滑鼠點擊事件，實現焦點切換與右鍵選單"""
        if event.type() == QEvent.Type.MouseButtonPress:
            widgets = getattr(self.win, 'video_widgets', [])
            frames = getattr(self.win, 'video_frames', [])

            target_idx = -1
            # 比對目前點擊的對象屬於第幾屏
            for i in range(max(len(widgets), len(frames))):
                w = widgets[i] if i < len(widgets) else None
                f = frames[i] if i < len(frames) else None

                if watched == w or watched == f:
                    target_idx = i
                    break
                if w and w.isAncestorOf(watched):
                    target_idx = i
                    break
                if f and hasattr(f, 'isAncestorOf') and f.isAncestorOf(watched):
                    target_idx = i
                    break

            if target_idx != -1:
                # 1. 滑鼠左鍵：切換焦點屏、更新邊框與聲音
                if event.button() == Qt.MouseButton.LeftButton:
                    if self.win.active_player_index != target_idx:
                        self.win.active_player_index = target_idx
                        self.update_screen_borders()
                        self._sync_audio_focus()

                # 2. 滑鼠右鍵：彈出分屏選單
                elif event.button() == Qt.MouseButton.RightButton:
                    w = widgets[target_idx] if target_idx < len(widgets) else frames[target_idx]
                    pos = event.pos() if hasattr(event, 'pos') else event.position().toPoint()
                    self._show_context_menu_for_widget(pos, w)

        return super().eventFilter(watched, event)

    def set_screen_layout(self, count):
        # 🎯 通知所有播放器依家係多屏定單屏模式
        for w in self.win.video_widgets:
            w.is_multi_mode = (count > 1)
        """🎯 設定分屏數量 (1~4屏) 並重新排版與掛載監聽"""
        self.win.setUpdatesEnabled(False)
        try:
            for i in range(len(self.win.video_widgets)):
                if i >= count:
                    widget = self.win.video_widgets[i]
                    mpv_inst = widget.mpv
                    if mpv_inst:
                        try:
                            if hasattr(widget, 'stop'):
                                widget.stop()
                            else:
                                mpv_inst.command('stop')
                        except Exception:
                            pass
                    widget.has_media = False
                    widget.update()

            while self.win.grid_layout.count():
                item = self.win.grid_layout.takeAt(0)
                if item and item.widget():
                    item.widget().hide()

            positions = {
                1: [(0, 0, 2, 2)],
                2: [(0, 0, 2, 1), (0, 1, 2, 1)],
                3: [(0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)],
                4: [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)]
            }

            layout_map = positions.get(count, positions[1])
            for idx, pos in enumerate(layout_map):
                if idx < len(self.win.video_frames):
                    frame = self.win.video_frames[idx]
                    self.win.grid_layout.addWidget(frame, pos[0], pos[1], pos[2], pos[3])
                    frame.show()
        finally:
            self.win.setUpdatesEnabled(True)

        if self.win.active_player_index >= count:
            self.win.active_player_index = 0

        self.update_screen_borders()
        self._sync_audio_focus()
        self.install_event_filters()
        # 🎯 B4終極修復：錯峰加載，防止同時4路網絡請求衝爆底層mpv
        if count > 1:
            for idx, w in enumerate(self.win.video_widgets):
                if w.has_media and not w._current_url:
                    continue
                # 用QTimer延遲啟動後面嘅屏幕，避免同時間發起4個loadfile
                QTimer.singleShot(idx * 200, lambda widx=idx: self.win.video_widgets[widx].play(self.win.video_widgets[widx]._current_url) if hasattr(self.win.video_widgets[widx], '_current_url') and self.win.video_widgets[widx]._current_url else None)

    def update_screen_borders(self):
        """🎯 更新分屏邊框高亮樣式與頂欄/頻道清單連動"""
        visible_frames = [f for f in self.win.video_frames if f.isVisible()]
        visible_count = len(visible_frames)
        accent_color = self.win.current_theme_accent

        for i, frame in enumerate(self.win.video_frames):
            if frame.isVisible():
                if visible_count <= 1:
                    frame.layout().setContentsMargins(0, 0, 0, 0)
                    frame.setStyleSheet("QFrame { background-color: #000000; border: none; }")
                else:
                    if i == self.win.active_player_index:
                        frame.layout().setContentsMargins(2, 2, 2, 2)
                        frame.setStyleSheet(f"QFrame {{ background-color: {accent_color}; border: none; }}")
                    else:
                        dim_border_color = "#2a2a38"
                        frame.layout().setContentsMargins(2, 2, 2, 2)
                        frame.setStyleSheet(f"QFrame {{ background-color: {dim_border_color}; border: none; }}")

        idx = self.win.active_player_index
        clist = getattr(self.win, 'channel_list', None)

        if 0 <= idx < len(self.win.video_widgets):
            w = self.win.video_widgets[idx]

            ch_info = getattr(w, 'channel_info', None) or {}
            ch_url = getattr(w, 'channel_url', None) or ch_info.get('url', '')
            ch_name = getattr(w, 'channel_name', None) or ch_info.get('name', '')

            if not ch_url or not ch_name:
                ch_obj = getattr(w, 'ch', None) or getattr(w, 'ch_data', None) or getattr(w, 'channel_data', None) or getattr(w, 'channel', None)
                if isinstance(ch_obj, dict):
                    ch_url = ch_url or ch_obj.get('url', '')
                    ch_name = ch_name or ch_obj.get('name', '')

            clean_name = ch_name.strip() if ch_name else ""
            has_media = getattr(w, 'has_media', False) or bool(ch_url or clean_name)

            # 直接讓 main_window 統一計算包含 EPG 的最新標題，防止舊邏輯覆蓋
            if hasattr(self.win, 'update_header_title'):
                self.win.update_header_title(channel_name=clean_name)

            if clist and clist.isVisible():
                matched_item = None
                if has_media and (ch_url or clean_name):
                    for row in range(clist.count()):
                        item = clist.item(row)
                        item_url = item.data(Qt.ItemDataRole.UserRole) or ''
                        item_ch = item.data(Qt.ItemDataRole.UserRole + 1) or {}
                        item_name = item_ch.get('name', '') if isinstance(item_ch, dict) else ''
                        clean_item_name = item_name.strip()

                        if ch_url and item_url == ch_url:
                            matched_item = item
                            break
                        elif clean_name and (clean_name == clean_item_name or clean_name in item.text()):
                            matched_item = item
                            break

                clist.blockSignals(True)
                if matched_item:
                    clist.setCurrentItem(matched_item)
                    matched_item.setSelected(True)
                    clist.scrollToItem(matched_item)
                else:
                    clist.clearSelection()
                    clist.setCurrentItem(None)
                clist.blockSignals(False)

    def _sync_audio_focus(self):
        """🎯 B5終極修復：採用標準 Mute 開關，點邊個屏邊個有聲，其他全部靜音，並同步控制欄"""
        if not self.win.video_widgets:
            return

        # 當前選中嘅屏幕索引
        target_idx = self.win.active_player_index

        # 確保索引唔越界
        if target_idx >= len(self.win.video_widgets):
            target_idx = 0

        # 🎯 A邏輯：點邊個屏邊個唔靜音，其他全部強制靜音
        for idx, widget in enumerate(self.win.video_widgets):
            try:
                widget.set_mute(idx != target_idx)
            except Exception:
                pass

        # 🎯 B邏輯：即時刷新底部控制欄嘅 UI 圖標 (🔊 / 🔇)
        # 確保控制欄顯示嘅係「當前選中屏幕」嘅真實狀態
        if hasattr(self.win, 'sync_controls_ui'):
            self.win.sync_controls_ui()
            
    def _show_context_menu_for_widget(self, pos, widget):
        # ===== 1. 如果已有 Menu 打開，先徹底關閉佢 =====
        if self.current_menu is not None:
            try:
                self.current_menu.close()
                self.current_menu.deleteLater()
            except:
                pass
            self.current_menu = None

        # ===== 2. 奪回焦點（同之前一樣） =====
        main_window = self.win
        user32 = ctypes.windll.user32
        hwnd = int(main_window.winId())
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        QCoreApplication.processEvents()

        # ===== 3. 建立 Menu =====
        menu = RoundedMenu(self.win)
        self.current_menu = menu   # 記住佢，方便下次關閉

        widgets = self.win.video_widgets or self.win.video_frames
        idx = widgets.index(widget) if widget in widgets else 0

        # ===== 4. 定義一個輔助函數：先關 Menu 再執行功能 =====
        def make_handler(func):
            def handler():
                # 關閉 Menu（即刻消失）
                if self.current_menu is not None:
                    self.current_menu.close()
                    self.current_menu.deleteLater()
                    self.current_menu = None
                # 然後執行真正功能
                func()
            return handler

        # 📊 統計資訊
        action_stats = QAction("📊 播放統計資訊", self.win)
        def stats_func():
            if hasattr(widget, 'toggle_stats'):
                widget.toggle_stats()
            elif hasattr(widget, 'mpv') and hasattr(widget.mpv, 'toggle_stats'):
                widget.mpv.toggle_stats()
        action_stats.triggered.connect(make_handler(stats_func))
        menu.addAction(action_stats)
        
        menu.addSeparator() #  分隔線

        # 🔗 複製 URL
        action_copy = QAction("🔗 複製當前串流 URL", self.win)
        def copy_func():
            url = getattr(widget, '_current_url', '')
            if not url and hasattr(widget, 'mpv'):
                url = getattr(widget.mpv, '_current_url', '')
            if url:
                QApplication.clipboard().setText(str(url))
        action_copy.triggered.connect(make_handler(copy_func))
        menu.addAction(action_copy)

        menu.addSeparator() #  分隔線
        
        # 📋 貼上並播放 URL (直擊核心極簡版)
        action_paste = QAction("📋 貼上並播放剪貼簿網址", self.win)
        def paste_func():
            text = QApplication.clipboard().text().strip()
            if text.startswith("http://") or text.startswith("https://"):
                self.win.drop_mgr.process_url(text)
        action_paste.triggered.connect(make_handler(paste_func))
        menu.addAction(action_paste)
        
        menu.addSeparator() #  分隔線

        # ❌ 關閉當前分屏
        action_close_cur = QAction(f"❌ 關閉/切斷第 {idx + 1} 屏", self.win)
        def close_cur_func():
            self.win._close_single_widget(widget)
        action_close_cur.triggered.connect(make_handler(close_cur_func))
        menu.addAction(action_close_cur)
        
        menu.addSeparator() #  分隔線

        # 🧹 關閉其他所有分屏
        action_close_others = QAction("🧹 關閉其他所有分屏", self.win)
        def close_others_func():
            for w in list(widgets):
                if w != widget:
                    self.win._close_single_widget(w)
        action_close_others.triggered.connect(make_handler(close_others_func))
        menu.addAction(action_close_others)

        # ===== 5. 非阻塞彈出（用 popup，唔用 exec） =====
        global_pos = widget.mapToGlobal(pos)
        menu.setFocus()
        menu.popup(global_pos)   # 立即返回，唔會卡住

        # ===== 6. 當 Menu 關閉時清理引用（萬一用戶㩒外面） =====
        def on_menu_hide():
            if self.current_menu == menu:
                self.current_menu = None
        menu.aboutToHide.connect(on_menu_hide)
