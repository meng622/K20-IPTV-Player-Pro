import os
from PyQt6.QtCore import QObject, QEvent, Qt
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFileDialog
from PyQt6.QtGui import QDropEvent

class DropOverlay(QWidget):
    """拖拽提示半透明遮罩層 (嚴格關閉 Drag&Drop 接收以實現 100% 事件穿透)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAcceptDrops(False)  # 關鍵：強制 Qt 將所有拖放事件穿透至父視窗
        
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 15, 28, 0.85);
                border: 3px dashed #007ACC;
                border-radius: 12px;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 18px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        layout = QVBoxLayout(self)
        self.label = QLabel("📥 拖放影音檔、字幕 (.srt/.ass) 或 M3U 播放清單至此", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.hide()

class DropManager(QObject):
    """全能拖拽分流與本地檔案開啟管理器"""
    
    PLAYLIST_EXTS = {'.m3u', '.m3u8'}
    MEDIA_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mp3', '.flac', '.wav', '.aac', '.ts'}
    SUB_EXTS = {'.srt', '.ass', '.vtt', '.ssa'}

    def __init__(self, main_window):
        super().__init__(main_window)
        self.win = main_window
        self.win.setAcceptDrops(True)
        self.win.installEventFilter(self)
        
        # 建立拖拽 Overlay 提示
        self.overlay = DropOverlay(self.win)
        self.overlay.resize(self.win.size())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self.win:
            evt_type = event.type()
            
            if evt_type == QEvent.Type.DragEnter:
                if event.mimeData().hasUrls() or event.mimeData().hasText():
                    event.acceptProposedAction()
                    self.overlay.resize(self.win.size())
                    self.overlay.show()
                    self.overlay.raise_()
                    return True

            elif evt_type == QEvent.Type.DragLeave:
                self.overlay.hide()
                return True

            elif evt_type == QEvent.Type.Drop:
                self.overlay.hide()
                self._handle_drop(event)
                return True

            elif evt_type == QEvent.Type.Resize:
                if self.overlay.isVisible():
                    self.overlay.resize(self.win.size())

        return super().eventFilter(watched, event)

    def _handle_drop(self, event: QDropEvent):
        """解析拖放數據"""
        mime = event.mimeData()
        print("📥 [DropManager] 檢測到 Drop 事件！開始解析數據...")
        
        if mime.hasUrls():
            for qurl in mime.urls():
                file_path = qurl.toLocalFile()
                if file_path:
                    print(f"📄 [DropManager] 讀取本地檔案: {file_path}")
                    self.process_file(file_path)
                else:
                    raw_url = qurl.toString()
                    print(f"🌐 [DropManager] 讀取網路 URL: {raw_url}")
                    self.process_url(raw_url)
            event.acceptProposedAction()

        elif mime.hasText():
            text = mime.text().strip()
            print(f"🔤 [DropManager] 讀取拖入文字: {text}")
            if text.startswith("http://") or text.startswith("https://"):
                self.process_url(text)
            event.acceptProposedAction()

    def process_file(self, file_path: str):
        """核心分流邏輯"""
        ext = os.path.splitext(file_path)[1].lower()

        if ext in self.PLAYLIST_EXTS:
            if hasattr(self.win, 'start_parse_m3u'):
                print(f"📦 [DropManager] 傳送 M3U 至 start_parse_m3u(): {file_path}")
                self.win.start_parse_m3u(file_path)
        elif ext in self.SUB_EXTS:
            self._load_subtitle(file_path)
        else:
            # 🎯 播放媒體
            self._play_media(file_path)
            # 🎯 自動紀錄至本地媒體播放列表 (上限 20 筆) 並切換視圖
            if hasattr(self.win, 'channel_mgr') and hasattr(self.win.channel_mgr, 'add_local_media_record'):
                file_name = os.path.basename(file_path)
                self.win.channel_mgr.add_local_media_record(file_name, file_path)

    def process_url(self, url: str):
        """網絡 URL 分流"""
        if url.endswith(".m3u") or url.endswith(".m3u8") or "m3u" in url.lower():
            if hasattr(self.win, 'start_parse_m3u'):
                self.win.start_parse_m3u(url)
        else:
            self._play_media(url)

    def _play_media(self, path_or_url: str):
        """對接真實的 video_widget.play() 方法"""
        active_idx = getattr(self.win, 'active_player_index', 0)
        screen_mgr = getattr(self.win, 'screen_mgr', None) or getattr(self.win, 'screen_manager', None)
        
        target_widget = None

        # 1. 嘗試從 ScreenManager 中尋找當前焦點視窗
        if screen_mgr:
            if hasattr(screen_mgr, 'get_player'):
                target_widget = screen_mgr.get_player(active_idx)
            elif hasattr(screen_mgr, 'widgets') and len(screen_mgr.widgets) > active_idx:
                target_widget = screen_mgr.widgets[active_idx]
            elif hasattr(screen_mgr, 'players') and len(screen_mgr.players) > active_idx:
                target_widget = screen_mgr.players[active_idx]

        # 2. 備援：直接調用主視窗預設 video_widget
        if not target_widget and hasattr(self.win, 'video_widget'):
            target_widget = self.win.video_widget

        # 3. 執行 .play(url)
        if target_widget and hasattr(target_widget, 'play'):
            print(f"▶️ [DropManager] 成功調用 target_widget.play(): {path_or_url}")
            target_widget.play(path_or_url)
        else:
            print(f"❌ [DropManager] 錯誤：無法定位具備 play() 方法的視窗組件！")

    def _load_subtitle(self, sub_path: str):
        """載入外掛字幕"""
        active_idx = getattr(self.win, 'active_player_index', 0)
        screen_mgr = getattr(self.win, 'screen_mgr', None) or getattr(self.win, 'screen_manager', None)
        player = None
        
        if screen_mgr and hasattr(screen_mgr, 'get_player'):
            player = screen_mgr.get_player(active_idx)
        elif hasattr(self.win, 'video_widget'):
            player = self.win.video_widget
            
        if player and hasattr(player, 'command'):
            print(f"💬 [DropManager] 載入字幕: {sub_path}")
            player.command("sub-add", sub_path)

    def open_file_dialog(self):
        """Ctrl+O 本地檔案對話框"""
        file_filter = (
            "所有支援格式 (*.mp4 *.mkv *.avi *.mov *.mp3 *.flac *.m3u *.m3u8 *.srt *.ass);;"
            "影音檔案 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.mp3 *.flac *.wav);;"
            "播放清單 (*.m3u *.m3u8);;"
            "字幕檔案 (*.srt *.ass *.vtt);;"
            "所有檔案 (*.*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(
            self.win, "開啟影音、字幕或播放清單", "", file_filter
        )
        if file_path:
            self.process_file(file_path)