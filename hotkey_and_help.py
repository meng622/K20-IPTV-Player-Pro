# [代碼起點]
from config import *  # 匯入配置

from dialogs import SettingsDialog  # 匯入設定
from m3u_manager import M3U管理主視窗  # 匯入管理
from config import _load_settings, _save_settings, _script_dir  # 匯入讀寫
from PyQt6.QtWidgets import QAbstractSpinBox, QTextEdit, QKeySequenceEdit  # 文字輸入控件

class HotkeyManager(QObject):  # 熱鍵類別
    """負責管理、儲存、加載與監聽所有自定義快捷鍵"""
    action_triggered = pyqtSignal(str)  # 觸發訊號

    def __init__(self, config_file=None):  # 初始化
        super().__init__()  # 呼叫父類
        self.config_file = config_file or os.path.join(_script_dir, "hotkeys.json")  # 固定放專案/exe 目錄
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
        }  # 預設按鍵
        self.hotkeys = self.load_hotkeys()  # 載入熱鍵

    def load_hotkeys(self):  # 載入熱鍵
        data = self.default_hotkeys.copy()  # 複製預設
        if os.path.exists(self.config_file):  # 檔案存在
            try:  # 嘗試讀取
                with open(self.config_file, "r", encoding="utf-8") as f:  # 開啟檔案
                    saved = json.load(f)  # 解析JSON
                    data.update(saved)  # 更新配置
            except Exception:  # 讀取錯誤
                pass  # 忽略錯誤
        return data  # 回傳資料

    def save_hotkeys(self):  # 儲存熱鍵
        try:  # 寫入失敗不要讓程式崩
            tmp_file = self.config_file + ".tmp"  # 暫存檔
            with open(tmp_file, "w", encoding="utf-8") as f:  # 開啟暫存
                json.dump(self.hotkeys, f, indent=4)  # 寫入JSON
            os.replace(tmp_file, self.config_file)  # 原子替換
        except OSError as e:  # 唯讀目錄等
            print(f"儲存快捷鍵失敗: {e}")  # 保留預設值繼續跑

    def set_hotkey(self, action, key_str):  # 設置按鍵
        self.hotkeys[action] = key_str  # 更新鍵值
        self.save_hotkeys()  # 寫入檔案

    def handle_key_event(self, event):  # 處理按鍵
        """主視窗 keyPressEvent 調用此處"""
        key_int = event.key()  # 取得鍵碼
        modifiers = int(event.modifiers().value)  # 取得修飾
        
        # 忽略單獨按下修飾鍵
        if key_int in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):  # 純修飾鍵
            return False  # 忽略不理

        seq_str = QKeySequence(key_int | modifiers).toString()  # 轉字串鍵

        # 🎯 快捷鍵：按 I 鍵切換數據面板
        if seq_str.lower() == "i":  # 按下I鍵
            self.action_triggered.emit("toggle_stats")  # 切換面板
            return True  # 攔截成功

        for action, target_seq in self.hotkeys.items():  # 比對熱鍵
            if seq_str.lower() == target_seq.lower():  # 匹配成功
                self.action_triggered.emit(action)  # 發送動作
                return True  # 攔截成功
        return False  # 未能匹配

class HotkeySettingDialog(QDialog):  # 熱鍵視窗
    """用戶自定義按鍵設置對話框"""
    def __init__(self, hotkey_mgr, parent=None):  # 初始化
        super().__init__(parent)  # 呼叫父類
        self.setWindowTitle("自定義快捷鍵設置")  # 標題設定
        self.mgr = hotkey_mgr  # 熱鍵管理
        self.edits = {}  # 編輯欄集

        layout = QVBoxLayout(self)  # 直排佈局
        form_layout = QFormLayout()  # 表單佈局

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
        }  # 動作對照

        for action, current_key in self.mgr.hotkeys.items():  # 遍歷熱鍵
            key_edit = QKeySequenceEdit(QKeySequence(current_key))  # 建立編輯
            # 📌 綁定即時監聽：限制單一按鍵與排他防重複
            key_edit.keySequenceChanged.connect(lambda seq, act=action: self._on_key_changed(act, seq))  # 監聽變動
            form_layout.addRow(action_names.get(action, action), key_edit)  # 加入表單
            self.edits[action] = key_edit  # 存入字典

        layout.addLayout(form_layout)  # 加入頁面

        btn_save = QPushButton("儲存變更")  # 儲存按鈕
        btn_save.clicked.connect(self.save_settings)  # 點擊儲存
        layout.addWidget(btn_save)  # 加入按鈕

    def _on_key_changed(self, changed_action, key_seq):  # 按鍵變更
        seq_str = key_seq.toString()  # 轉為字串
        if not seq_str:  # 字串空白
            return  # 結束執行

        # 1. 解決重複 F11, F11 問題：強制只保留最後一次按下的單一按鍵
        if "," in seq_str:  # 重複連按
            seq_str = seq_str.split(",")[-1].strip()  # 取最後鍵
            edit = self.edits[changed_action]  # 取得組件
            edit.blockSignals(True)  # 阻斷訊號
            edit.setKeySequence(QKeySequence(seq_str))  # 更新單鍵
            edit.blockSignals(False)  # 恢復訊號

        # 2. 解決快捷鍵衝突問題：若其他功能已有相同按鍵，自動清空舊功能
        for action, edit in self.edits.items():  # 檢查衝突
            if action != changed_action:  # 非當前項
                if edit.keySequence().toString().lower() == seq_str.lower():  # 發生重複
                    edit.blockSignals(True)  # 阻斷訊號
                    edit.clear()  # 清空舊鍵
                    edit.blockSignals(False)  # 恢復訊號

    def save_settings(self):  # 儲存設定
        for action, key_edit in self.edits.items():  # 遍歷欄位
            new_key = key_edit.keySequence().toString()  # 取得新鍵
            self.mgr.set_hotkey(action, new_key)  # 保存熱鍵
        self.accept()  # 關閉視窗

class HotkeyAndHelpManager(QObject):  # 總管類別
    """管理 Hotkey 觸發響應與 Dialog 對話框"""
    def __init__(self, main_window):  # 初始化
        super().__init__()  # 呼叫父類
        self.win = main_window  # 綁定主視
        self.hotkey_mgr = HotkeyManager()  # 建立熱鍵
        self.hotkey_mgr.action_triggered.connect(self.dispatch_action)  # 連接分發
        
        # 升級為全域監聽，確保 PiP 視窗取得焦點時也能接收快捷鍵
        app = QApplication.instance()  # 取得應用
        if app:  # 實體存在
            app.installEventFilter(self)  # 全域過濾
        else:  # 實體不存在
            self.win.installEventFilter(self)  # 視窗過濾

    def eventFilter(self, watched, event):  # 事件過濾
        """攔截鍵盤按下事件並觸發快捷鍵"""
        if event.type() == QEvent.Type.KeyPress:  # 按下按鍵
            # 📌 第一性原則：若有任何彈窗（如快捷鍵設置對話框）開啟，自動屏蔽主視窗快捷鍵響應
            if QApplication.activeModalWidget() is not None:  # 有模態窗
                return super().eventFilter(watched, event)  # 跳過響應

            # 焦點在文字輸入控件時，按鍵要留給輸入（否則搜尋框打 s/p 會被當熱鍵）
            focus = QApplication.focusWidget()  # 當前焦點
            if isinstance(focus, (QLineEdit, QAbstractSpinBox, QTextEdit, QKeySequenceEdit)):  # 文字輸入
                return super().eventFilter(watched, event)  # 放行

            if event.isAutoRepeat():  # 長按不重複觸發
                return True  # 吃掉重複鍵

            if self.hotkey_mgr.handle_key_event(event):  # 處理熱鍵
                return True  # 攔截成功
        return super().eventFilter(watched, event)  # 預設處理

    def dispatch_action(self, action):  # 動作分發
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
        }  # 動作對照
        handler = actions_map.get(action)  # 取得函數
        if handler:  # 函數存在
            handler()  # 執行函數

    def open_help_dialog(self):  # 開啟說明
        """動態顯示當前設定的快捷鍵指南"""
        hk = self.hotkey_mgr.hotkeys  # 讀取熱鍵
        msg = QMessageBox(self.win)  # 建訊息框
        msg.setWindowTitle("快捷鍵說明")  # 標題設定
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
        )  # 內容設定
        msg.exec()  # 顯示對話

    def open_hotkey_settings(self):  # 熱鍵設定
        """開啟快捷鍵自定義設定面板"""
        dlg = HotkeySettingDialog(self.hotkey_mgr, self.win)  # 建熱鍵窗
        dlg.exec()  # 顯示對話

    def open_settings_dialog(self):  # 偏好設定
        dlg = SettingsDialog(self.win, config=self.win._settings)  # 建設定窗
        if dlg.exec() == QDialog.DialogCode.Accepted:  # 按下確認
            new_settings = dlg.get_settings()  # 取得設定
            self.win._settings.update(new_settings)  # 更新字典
            self.win.hw_enabled = new_settings.get("hwdec", True)  # 硬解開關
            self.win.auto_play_last = new_settings.get("auto_play_last", False)  # 自動播放
            self.win.cache_mb = new_settings.get("cache_mb", 100)  # 快取大小
            try:  # 立即套用到目前播放器
                cache_mb = max(10, min(int(self.win.cache_mb), 500))  # 限制範圍
            except (TypeError, ValueError):  # 設定值異常
                cache_mb = 100  # 預設
            for player in getattr(self.win, "video_widgets", []):  # 所有分屏
                player.cache_mb = cache_mb  # 下次初始化用
                if getattr(player, "_ctx", None):  # 已在播放
                    limit_mb = min(cache_mb, 15) if player.is_multi_mode else cache_mb  # 多屏上限
                    player._set_property_string("demuxer-max-bytes", f"{limit_mb}M")  # 即時生效
                    player._set_property_string("cache-secs", str(max(5, min(30, limit_mb // 10))))  # 同步秒數
            _save_settings(self.win._settings)  # 儲存檔案
            if hasattr(self.win, '_update_hw_btn_style'):  # 方法存在
                self.win._update_hw_btn_style()  # 更新按鈕

    def open_m3u_manager(self):  # 列表管理
        dlg = M3U管理主視窗(self.win, sources=self.win.m3u_sources, current_url=self.win.current_m3u_url)  # 建管理窗
        if dlg.exec() == QDialog.DialogCode.Accepted:  # 按下確認
            sources, selected_url = dlg.get_data()  # 取得資料
            self.win.m3u_sources = sources  # 更新來源
            if selected_url:  # 有選擇網址
                self.win.current_m3u_url = selected_url  # 更新網址
                self.win._settings["current_m3u_url"] = selected_url  # 寫入設定
            self.win._settings["m3u_sources"] = sources  # 寫入來源
            _save_settings(self.win._settings)  # 儲存檔案
            if selected_url and hasattr(self.win, 'start_parse_m3u'):  # 網址有效
                self.win.start_parse_m3u(selected_url)  # 解析網址
# [代碼終點]