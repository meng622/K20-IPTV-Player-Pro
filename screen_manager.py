# screen_manager.py
from PyQt6.QtCore import QObject, QEvent, Qt
from PyQt6.QtWidgets import QMenu, QLabel
from config import *

class ScreenManager(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.win = main_window
        # 綁定相容接口，防止 main_window 呼叫舊方法時報錯
        self.win._event_filter_install_for_widgets = self.install_event_filters

    def install_event_filters(self):
        """🎯 自動為所有分屏框架與播放組件安裝事件過濾器"""
        frames = getattr(self.win, 'video_frames', [])
        widgets = getattr(self.win, 'video_widgets', [])

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
                if w and hasattr(w, 'isAncestorOf') and w.isAncestorOf(watched):
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
        """🎯 設定分屏數量 (1~4屏) 並重新排版與掛載監聽"""
        self.win.setUpdatesEnabled(False)
        try:
            for i in range(len(self.win.video_widgets)):
                if i >= count:
                    widget = self.win.video_widgets[i]
                    mpv_inst = getattr(widget, 'mpv', None) or getattr(widget, 'player', None)
                    if mpv_inst:
                        try:
                            mpv_inst.command('loadfile', '', 'replace')
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

    def update_screen_borders(self):
        """🎯 更新分屏邊框高亮樣式與頂欄/頻道清單連動"""
        visible_frames = [f for f in self.win.video_frames if f.isVisible()]
        visible_count = len(visible_frames)
        accent_color = getattr(self.win, 'current_theme_accent', '#8b5cf6')

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

            top_text = f"[直播流] - {clean_name}" if (has_media and clean_name) else "[直播流] - "
            for lbl in self.win.findChildren(QLabel):
                if lbl.text() and "[直播流]" in lbl.text():
                    lbl.setText(top_text)
                    break

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
        """🎯 同步音量焦點 (獨佔播放當前焦點屏的聲音)"""
        if not self.win.video_widgets:
            return

        vol_val = self.win.vol_slider.value() if getattr(self.win, 'vol_slider', None) and self.win.vol_slider.value() > 0 else 100

        sound_target_idx = self.win.active_player_index
        if not self.win.video_widgets[self.win.active_player_index].has_media:
            for i, w in enumerate(self.win.video_widgets):
                if w.has_media:
                    sound_target_idx = i
                    break

        for idx, widget in enumerate(self.win.video_widgets):
            mpv_inst = getattr(widget, 'mpv', None) or getattr(widget, 'player', None)
            if not mpv_inst:
                continue

            try:
                target_vol = vol_val if (idx == sound_target_idx and widget.has_media) else 0
                current_vol = getattr(mpv_inst, 'volume', None)
                if current_vol != target_vol:
                    mpv_inst.volume = target_vol
            except Exception:
                pass

    def _show_context_menu_for_widget(self, pos, widget):
        """🎯 分屏右鍵功能選單"""
        menu = QMenu(self.win)
        widgets = self.win.video_widgets or self.win.video_frames
        idx = widgets.index(widget) if widget in widgets else 0

        action_close = menu.addAction(f"❌ 關閉/切斷第 {idx + 1} 屏")
        action_close_others = menu.addAction("🧹 關閉其他所有分屏")

        selected = menu.exec(widget.mapToGlobal(pos))
        if selected == action_close:
            if hasattr(self.win, '_close_single_widget'):
                self.win._close_single_widget(widget)
        elif selected == action_close_others:
            if hasattr(self.win, '_close_single_widget'):
                for w in widgets:
                    if w != widget:
                        self.win._close_single_widget(w)