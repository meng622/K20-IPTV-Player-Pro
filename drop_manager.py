# [代碼起點]
from config import *  # 匯入配置

# =================================================================================
# 拖拽遮罩
# =================================================================================
class DropOverlay(QWidget):  # 遮罩圖層
    # ----- 建構子 -----
    def __init__(self, parent=None):  # 初始化
        super().__init__(parent)                           # 呼叫父類
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)  # 事件穿透
        self.setAcceptDrops(False)                         # 關閉拖放

        self.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 18px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)  # 遮罩樣式
        layout = QVBoxLayout(self)                         # 垂直佈局
        self.label = QLabel("📥 拖放影音檔、字幕 (.srt/.ass) 或 M3U 播放清單至此", self)  # 提示文字
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 文字置中
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignCenter)  # 加提示標
        self.hide()                                        # 預設隱藏

# =================================================================================
# 拖拽管理器
# =================================================================================
class DropManager(QObject):  # 拖拽管理
    
    PLAYLIST_EXTS = {'.m3u', '.m3u8'}                     # 清單副檔
    MEDIA_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mp3', '.flac', '.wav', '.aac', '.ts'}  # 影音副檔
    SUB_EXTS = {'.srt', '.ass', '.vtt', '.ssa'}          # 字幕副檔

    # ----- 建構子 -----
    def __init__(self, main_window):  # 初始化
        super().__init__(main_window)                     # 呼叫父類
        self.win = main_window                            # 主視窗
        self.win.setAcceptDrops(True)                     # 開放拖放
        self.win.installEventFilter(self)                 # 安裝過濾

        self.overlay = DropOverlay(self.win)              # 建遮罩層
        self.overlay.resize(self.win.size())              # 同步尺寸

    # ----- 事件過濾 -----
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # 過濾事件
        if watched == self.win:                           # 目標主窗
            evt_type = event.type()                       # 事件類型

            if evt_type == QEvent.Type.DragEnter:  # 拖入事件
                if event.mimeData().hasUrls() or event.mimeData().hasText():  # 包含數據
                    event.acceptProposedAction()          # 接受拖放
                    self.overlay.resize(self.win.size())  # 同步尺寸
                    self.overlay.setWindowOpacity(0.85)   # 設定透明
                    self.overlay.show()                   # 顯示遮罩
                    self.overlay.raise_()                 # 置頂遮罩
                    return True  # 完成處理

            elif evt_type == QEvent.Type.DragLeave:  # 拖離事件
                self.overlay.hide()                       # 隱藏遮罩
                return True  # 完成處理

            elif evt_type == QEvent.Type.Drop:  # 放下事件
                self.overlay.hide()                       # 隱藏遮罩
                self._handle_drop(event)                  # 處理數據
                return True  # 完成處理

            elif evt_type == QEvent.Type.Resize:  # 縮放事件
                if self.overlay.isVisible():              # 遮罩可見
                    self.overlay.resize(self.win.size())  # 同步縮放

        return super().eventFilter(watched, event)       # 基類處理

    # ----- 解析數據 -----
    def _handle_drop(self, event: QDropEvent):  # 解析數據
        mime = event.mimeData()                           # 取數據物件
        print("📥 [DropManager] 檢測到 Drop 事件！開始解析數據...")  # 印出日誌

        if mime.hasUrls():  # 含有網址
            for qurl in mime.urls():                      # 遍歷網址
                file_path = qurl.toLocalFile()            # 轉本地路徑
                if file_path:  # 本地檔案
                    print(f"📄 [DropManager] 讀取本地檔案: {file_path}")  # 印出檔案
                    self.process_file(file_path)          # 處理檔案
                else:  # 網路網址
                    raw_url = qurl.toString()             # 取原始網址
                    print(f"🌐 [DropManager] 讀取網路 URL: {raw_url}")  # 印出網址
                    self.process_url(raw_url)             # 處理網址
            event.acceptProposedAction()                  # 確認接受

        elif mime.hasText():  # 含有文字
            text = mime.text().strip()                    # 清理文字
            print(f"🔤 [DropManager] 讀取拖入文字: {text}")  # 印出文字
            if text.startswith("http://") or text.startswith("https://"):  # 是否網址
                self.process_url(text)                    # 處理網址
            event.acceptProposedAction()  # 確認接受

    # ----- 檔案分流 -----
    def process_file(self, file_path: str):  # 檔案分流
        ext = os.path.splitext(file_path)[1].lower()      # 取副檔名

        if ext in self.PLAYLIST_EXTS:  # 播放清單
            print(f"📦 [DropManager] 傳送 M3U 至 start_parse_m3u(): {file_path}")  # 印出訊息
            self.win.start_parse_m3u(file_path)           # 解析清單（路徑）

        elif ext in self.SUB_EXTS:  # 字幕檔案
            self._load_subtitle(file_path)                # 載入字幕（路徑）

        else:  # 媒體檔案
            self._play_media(file_path)                   # 播放媒體（路徑）

            file_name = os.path.basename(file_path)       # 提取檔名（路徑）
            self.win.channel_mgr.add_local_media_record(file_name, file_path)  # 記錄歷史（文件名, 路徑）

    # ----- URL分流 -----
    def process_url(self, url: str):  # 網址分流
        if url.endswith(".m3u") or url.endswith(".m3u8") or "m3u" in url.lower():  # 是否清單
            print(f"🌐 [DropManager] 傳送 URL 至 start_parse_m3u(): {url}")  # 印出日誌
            self.win.start_parse_m3u(url)                 # 解析網址
        else:  # 串流媒體
            self._play_media(url)                         # 播放串流

    # ----- 媒體播放 -----
    def _play_media(self, path_or_url: str):  # 播放媒體
        active_idx = self.win.active_player_index         # 取分屏索引
        screen_mgr = self.win.screen_mgr                  # 取分屏管理

        target_widget = None                              # 目標組件

        if screen_mgr:  # 管理器存在
            target_widget = self.win.video_widgets[active_idx]  # 取對應組件

        if not target_widget:  # 無對應組件
            target_widget = self.win.video_widget  # 取預設組件

        if target_widget and hasattr(target_widget, 'play'):  # 支援播放
            print(f"▶️ [DropManager] 成功調用 target_widget.play(): {path_or_url}")  # 印出成功
            target_widget.play(path_or_url)               # 執行播放
        else:  # 無法播放
            print(f"❌ [DropManager] 錯誤：無法定位具備 play() 方法的視窗組件！")  # 印出錯誤

    # ----- 載入字幕 -----
    def _load_subtitle(self, sub_path: str):  # 載入字幕
        active_idx = self.win.active_player_index  # 取分屏索引
        screen_mgr = self.win.screen_mgr  # 取分屏管理
        player = None  # 播放器變數

        if screen_mgr and hasattr(screen_mgr, 'get_player'):  # 支援取播放器
            player = screen_mgr.get_player(active_idx)  # 取播放器
        elif hasattr(self.win, 'video_widget'):  # 有預設組件
            player = self.win.video_widget                # 設預設組件

        if player and hasattr(player, 'command'):  # 支援指令
            print(f"💬 [DropManager] 載入字幕: {sub_path}")  # 印出字幕
            player.command("sub-add", sub_path)           # 嵌入字幕

    # ----- 檔案視窗 -----
    def open_file_dialog(self):  # 開檔對話
        file_filter = (
            "所有支援格式 (*.mp4 *.mkv *.avi *.mov *.mp3 *.flac *.m3u *.m3u8 *.srt *.ass);;"
            "影音檔案 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.mp3 *.flac *.wav);;"
            "播放清單 (*.m3u *.m3u8);;"
            "字幕檔案 (*.srt *.ass *.vtt);;"
            "所有檔案 (*.*)"
        )  # 格式篩選
        file_path, _ = QFileDialog.getOpenFileName(
            self.win, "開啟影音、字幕或播放清單", "", file_filter
        )  # 選取檔案
        if file_path:                                     # 選取成功
            self.process_file(file_path)                  # 處理檔案
# [代碼終點]