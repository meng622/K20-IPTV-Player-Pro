# hotkey_and_help.py
from config import *  # 匯入配置

from dialogs import SettingsDialog
from m3u_manager import M3U管理主視窗
from config import _load_settings, _save_settings

class HotkeyManager(QObject):
    """負責管理、儲存、加載與監聽所有自定義快捷鍵"""
    action_triggered = pyqtSignal(str)

    def __init__(self, config_file="hotkeys.json"):
        super().__init__()
        self.config_file = config_file
        # 預設按鍵表（原硬編碼快捷鍵）
        self.default_hotkeys = {
            "seek_backward": "Left",
            "seek_forward": "Right",
            "play_pause": "Space",
            "toggle_fullscreen": "F",
            "exit_fullscreen": "Esc",
            "volume_up": "Up",
            "volume_down": "Down",
            "snapshot": "S",
            "toggle_pip": "P",
            "open_file": "Ctrl+O"
        }
        self.hotkeys = self.load_hotkeys()

    def load_hotkeys(self):
        data = self.default_hotkeys.copy()
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    data.update(saved)
            except Exception:
                pass
        return data

    def save_hotkeys(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.hotkeys, f, indent=4)

    def set_hotkey(self, action, key_str):
        self.hotkeys[action] = key_str
        self.save_hotkeys()

    def handle_key_event(self, event):
        """主視窗 keyPressEvent 調用此處"""
        key_int = event.key()
        modifiers = int(event.modifiers().value)
        
        # 忽略單獨按下修飾鍵
        if key_int in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return False

        seq_str = QKeySequence(key_int | modifiers).toString()

        # 🎯 快捷鍵：按 I 鍵切換數據面板
        if seq_str.lower() == "i":
            self.action_triggered.emit("toggle_stats")
            return True

        for action, target_seq in self.hotkeys.items():
            if seq_str.lower() == target_seq.lower():
                self.action_triggered.emit(action)
                return True
        return False

class HotkeySettingDialog(QDialog):
    """用戶自定義按鍵設置對話框"""
    def __init__(self, hotkey_mgr, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定義快捷鍵設置")
        self.mgr = hotkey_mgr
        self.edits = {}

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        action_names = {
            "seek_backward": "快退 5 秒",
            "seek_forward": "快進 5 秒",
            "play_pause": "播放 / 暫停",
            "toggle_fullscreen": "切換全屏",
            "exit_fullscreen": "退出全屏",
            "volume_up": "調高音量",
            "volume_down": "調低音量",
            "snapshot": "截圖",
            "toggle_pip": "切換畫中畫 (PiP)",
            "open_file": "開啟本地檔案 (Ctrl+O)"
        }

        for action, current_key in self.mgr.hotkeys.items():
            key_edit = QKeySequenceEdit(QKeySequence(current_key))
            # 📌 綁定即時監聽：限制單一按鍵與排他防重複
            key_edit.keySequenceChanged.connect(lambda seq, act=action: self._on_key_changed(act, seq))
            form_layout.addRow(action_names.get(action, action), key_edit)
            self.edits[action] = key_edit

        layout.addLayout(form_layout)

        btn_save = QPushButton("儲存變更")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)

    def _on_key_changed(self, changed_action, key_seq):
        seq_str = key_seq.toString()
        if not seq_str:
            return

        # 1. 解決重複 F11, F11 問題：強制只保留最後一次按下的單一按鍵
        if "," in seq_str:
            seq_str = seq_str.split(",")[-1].strip()
            edit = self.edits[changed_action]
            edit.blockSignals(True)
            edit.setKeySequence(QKeySequence(seq_str))
            edit.blockSignals(False)

        # 2. 解決快捷鍵衝突問題：若其他功能已有相同按鍵，自動清空舊功能
        for action, edit in self.edits.items():
            if action != changed_action:
                if edit.keySequence().toString().lower() == seq_str.lower():
                    edit.blockSignals(True)
                    edit.clear()  # 自動抹除重複的舊按鍵
                    edit.blockSignals(False)

    def save_settings(self):
        for action, key_edit in self.edits.items():
            new_key = key_edit.keySequence().toString()
            self.mgr.set_hotkey(action, new_key)  # 保存最新的單一快捷鍵（被清空的寫入空值）
        self.accept()

class HotkeyAndHelpManager(QObject):
    """管理 Hotkey 觸發響應與 Dialog 對話框"""
    def __init__(self, main_window):
        super().__init__()
        self.win = main_window
        self.hotkey_mgr = HotkeyManager()
        self.hotkey_mgr.action_triggered.connect(self.dispatch_action)
        
        # 升級為全域監聽，確保 PiP 視窗取得焦點時也能接收快捷鍵
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
        else:
            self.win.installEventFilter(self)

    def eventFilter(self, watched, event):
        """攔截鍵盤按下事件並觸發快捷鍵"""
        if event.type() == QEvent.Type.KeyPress:
            # 📌 第一性原則：若有任何彈窗（如快捷鍵設置對話框）開啟，自動屏蔽主視窗快捷鍵響應
            if QApplication.activeModalWidget() is not None:
                return super().eventFilter(watched, event)

            if self.hotkey_mgr.handle_key_event(event):
                return True
        return super().eventFilter(watched, event)

    def dispatch_action(self, action):
        """將熱鍵動作分發給主視窗函數"""
        actions_map = {
            "seek_backward": lambda: self.win.seek_offset(-5),
            "seek_forward": lambda: self.win.seek_offset(5),
            "play_pause": self.win.toggle_play,
            "toggle_fullscreen": self.win.toggle_fullscreen,
            "exit_fullscreen": self.win._esc_handler,
            "volume_up": self.win._volume_up,
            "volume_down": self.win._volume_down,
            "snapshot": self.win.take_snapshot,
            "toggle_pip": lambda: self.win.pip_mgr.toggle(),
            "open_file": self.win.drop_mgr.open_file_dialog,
        }
        handler = actions_map.get(action)
        if handler:
            handler()

    def open_help_dialog(self):
        """動態顯示當前設定的快捷鍵指南"""
        hk = self.hotkey_mgr.hotkeys
        msg = QMessageBox(self.win)
        msg.setWindowTitle("快捷鍵說明")
        msg.setText(
            "<b>快捷鍵與操作指南：</b><br><br>"
            f"• <b>{hk.get('play_pause', 'Space')}</b> : 播放 / 暫停 (選中屏)<br>"
            f"• <b>{hk.get('seek_backward', 'Left')} / {hk.get('seek_forward', 'Right')}</b> : 快退 / 快進 5 秒<br>"
            f"• <b>{hk.get('volume_up', 'Up')} / {hk.get('volume_down', 'Down')}</b> : 調高 / 調低音量<br>"
            f"• <b>{hk.get('toggle_fullscreen', 'F11')}</b> : 切換全屏<br>"
            f"• <b>{hk.get('exit_fullscreen', 'Esc')}</b> : 退出全屏<br>"
            f"• <b>{hk.get('snapshot', 'S')}</b> : 截屏<br>"
            f"• <b>{hk.get('toggle_pip', 'P')}</b> : 切換畫中畫 (PiP)<br>"
            "• <b>點擊分屏</b> : 切換控制焦點與音聲<br>"
        )
        msg.exec()

    def open_hotkey_settings(self):
        """開啟快捷鍵自定義設定面板"""
        dlg = HotkeySettingDialog(self.hotkey_mgr, self.win)
        dlg.exec()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self.win, config=self.win._settings)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_settings = dlg.get_settings()
            self.win._settings.update(new_settings)
            self.win.hw_enabled = new_settings.get("hwdec", True)
            self.win.auto_play_last = new_settings.get("auto_play_last", False)
            self.win.cache_mb = new_settings.get("cache_mb", 100)
            _save_settings(self.win._settings)
            if hasattr(self.win, '_update_hw_btn_style'):
                self.win._update_hw_btn_style()

    def open_m3u_manager(self):
        dlg = M3U管理主視窗(self.win, sources=self.win.m3u_sources, current_url=self.win.current_m3u_url)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            sources, selected_url = dlg.get_data()
            self.win.m3u_sources = sources
            if selected_url:
                self.win.current_m3u_url = selected_url
                self.win._settings["current_m3u_url"] = selected_url
            self.win._settings["m3u_sources"] = sources
            _save_settings(self.win._settings)
            if selected_url and hasattr(self.win, 'start_parse_m3u'):
                self.win.start_parse_m3u(selected_url)
