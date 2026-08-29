#epg_panel.py
from config import *  # 匯入配置

from skin import IconManager
from channel_panel import _clean_epg_key

class EPGPanelWidget(QWidget):
    def __init__(self, main_win):
        super().__init__(main_win)
        self.main_win = main_win
        self.setObjectName("epg_panel")
        self.setMinimumWidth(420)
        self.setMaximumWidth(16777215)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self._init_ui()

    def _init_ui(self):
        """初始化右側 EPG 節目表面板 UI"""
        epg_layout = QVBoxLayout(self)
        epg_layout.setContentsMargins(12, 12, 12, 12)
        epg_layout.setSpacing(8)

        epg_title_layout = QHBoxLayout()
        epg_title_layout.setContentsMargins(0, 0, 0, 0)
        epg_title_layout.setSpacing(6)

        epg_icon_lbl = QLabel()
        epg_icon = IconManager.get_icon("epg", color="#ffffff", size=18)
        epg_icon_lbl.setPixmap(epg_icon.pixmap(18, 18))

        epg_title_txt = QLabel("節目表 (EPG)")
        epg_title_txt.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")

        epg_title_layout.addWidget(epg_icon_lbl)
        epg_title_layout.addWidget(epg_title_txt)
        epg_title_layout.addStretch()

        epg_layout.addLayout(epg_title_layout)

        self.epg_list_widget = QListWidget()
        self.epg_list_widget.setObjectName("epg_list_widget")
        
        epg_layout.addWidget(self.epg_list_widget, 1)

        # 保持與主視窗相容之屬性綁定
        self.main_win.epg_list_widget = self.epg_list_widget

    def toggle_panel(self):
        """切換右側 EPG 節目表顯示狀態"""
        is_opening = not self.isVisible()
        self.setVisible(is_opening)

        QTimer.singleShot(20, self.main_win._auto_adjust_bottom_controls)

        if is_opening:
            raw_name = getattr(self.main_win, 'current_channel_name', '')
            if not raw_name:
                idx = getattr(self.main_win, 'active_player_index', 0)
                if hasattr(self.main_win, 'video_widgets') and 0 <= idx < len(self.main_win.video_widgets):
                    w = self.main_win.video_widgets[idx]
                    raw_name = getattr(w, 'channel_name', '') or getattr(w, 'channel_info', {}).get('name', '')

            clean_name = re.sub(r'^\d+\.\s*', '', raw_name)
            clean_name = re.sub(r'\s+\[(?!HD|SD|4K|FHD).*?\]$', '', clean_name, flags=re.IGNORECASE).strip()
            if not clean_name:
                clean_name = raw_name.strip()

            print(f"📺 [DEBUG] 打開 EPG 面板！目標頻道名稱: '{clean_name}'")

            if clean_name:
                self.main_win.current_channel_name = clean_name

            self.update_epg_content(clean_name)

    def update_epg_content(self, channel_name=None):
        """更新 EPG 節目表內容（回歸內存字典模式）"""
        if channel_name:
            self.main_win.current_channel_name = channel_name

        if not hasattr(self, 'epg_list_widget') or self.epg_list_widget is None:
            return

        self.epg_list_widget.clear()
        current_ch = getattr(self.main_win, 'current_channel_name', '')
        if not current_ch or "請點擊左側頻道" in current_ch:
            self.epg_list_widget.addItem("⚠️ 請先選擇並播放頻道")
            return

        # ✅ 重點：直接讀取內存字典！
        epg_db_data = getattr(self.main_win, 'epg_data', {}) or getattr(self.main_win, 'epg_cache', {})
        if not epg_db_data:
            self.epg_list_widget.addItem("⚠️ EPG 資料庫為空，請確定已載入 EPG 網址")
            return

        # 構建匹配 Key（同 channel_panel 一模一樣）
        from epg_manager import clean_channel_name
        keys_to_check = set()
        raw_name = current_ch.replace("📺", "").replace("⭐", "").replace("🕒", "").strip()
        if raw_name:
            keys_to_check.add(raw_name.lower())
            keys_to_check.add(clean_channel_name(raw_name))
        
        ch_obj = getattr(self.main_win, 'current_channel_obj', {}) or {}
        if isinstance(ch_obj, dict):
            if ch_obj.get('tvg_id'):
                keys_to_check.add(str(ch_obj.get('tvg_id')).lower().strip())
                keys_to_check.add(clean_channel_name(ch_obj.get('tvg_id')))
            if ch_obj.get('tvg_name'):
                keys_to_check.add(str(ch_obj.get('tvg_name')).lower().strip())
                keys_to_check.add(clean_channel_name(ch_obj.get('tvg_name')))

        keys_to_check.discard("")

        matched_items = []
        for k in keys_to_check:
            if k in epg_db_data:
                matched_items = epg_db_data[k]
                break

        if not matched_items:
            self.epg_list_widget.addItem(f"⚠️ 頻道: {raw_name}\n未找到 EPG 節目單")
            return

        # 去重並顯示
        seen_progs = set()
        unique_progs = []
        for p in matched_items:
            prog_tuple = (p.get('start'), p.get('stop'), p.get('title'))
            if prog_tuple not in seen_progs:
                seen_progs.add(prog_tuple)
                unique_progs.append(p)

        now = datetime.now()
        for prog in unique_progs:
            start_str = prog.get('start', '')
            stop_str = prog.get('stop', '')
            time_fmt = "--:--"
            is_current = False
            try:
                s_raw = start_str.split()[0][:14]
                e_raw = stop_str.split()[0][:14]
                if len(s_raw) >= 12:
                    st = datetime.strptime(s_raw.ljust(14, '0'), "%Y%m%d%H%M%S")
                    time_fmt = st.strftime("%H:%M")
                    if len(e_raw) >= 12:
                        et = datetime.strptime(e_raw.ljust(14, '0'), "%Y%m%d%H%M%S")
                        if st <= now <= et:
                            is_current = True
            except Exception:
                pass

            prefix = "▶ " if is_current else "   "
            item_text = f"{prefix}[{time_fmt}]  {prog.get('title', '未知節目')}"
            list_item = QListWidgetItem(item_text)
            if is_current:
                list_item.setForeground(QColor("#00f2fe"))
                self.epg_list_widget.addItem(list_item)
                self.epg_list_widget.setCurrentItem(list_item)
                
                # 🎯 終極修正：鎖定「行索引」，唔好鎖死物件！
                target_row = self.epg_list_widget.row(list_item)
                QTimer.singleShot(50, lambda r=target_row: self.epg_list_widget.scrollToItem(
                    self.epg_list_widget.item(r), QAbstractItemView.ScrollHint.PositionAtCenter
                ))
            else:
                self.epg_list_widget.addItem(list_item)
