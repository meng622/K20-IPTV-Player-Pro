# drop_manager.py
from config import *  # 匯入所有 Qt 組件與設定

# =================================================================================
# 拖拽提示半透明遮罩層（純穿透，不攔截事件）
# =================================================================================
class DropOverlay(QWidget):
    """拖拽提示半透明遮罩層 (嚴格關閉 Drag&Drop 接收以實現 100% 事件穿透)"""
    
    # ----- 建構子：建立透明遮罩並隱藏 ------------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)                           # 呼叫父類建構子
        # 設定滑鼠事件完全穿透（點擊與拖動均不攔截）
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAcceptDrops(False)                         # 關鍵：強制所有拖放事件穿透至父視窗

        # 樣式表：純透明背景 + 白色文字（不干擾底層影片）
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
        """)
        layout = QVBoxLayout(self)                         # 垂直佈局
        self.label = QLabel("📥 拖放影音檔、字幕 (.srt/.ass) 或 M3U 播放清單至此", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 文字置中
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignCenter)  # 加入標籤（不拉伸）
        self.hide()                                        # 預設隱藏

# =================================================================================
# 全能拖拽分流與本地檔案開啟管理器
# =================================================================================
class DropManager(QObject):
    """全能拖拽分流與本地檔案開啟管理器"""
    
    # 靜態集合：定義支援的副檔名類型
    PLAYLIST_EXTS = {'.m3u', '.m3u8'}                     # 播放清單
    MEDIA_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mp3', '.flac', '.wav', '.aac', '.ts'}  # 影音媒體
    SUB_EXTS = {'.srt', '.ass', '.vtt', '.ssa'}          # 字幕檔案

    # ----- 建構子：綁定主視窗並安裝事件過濾器 ----------------------------------------
    def __init__(self, main_window):
        super().__init__(main_window)                     # 呼叫父類建構子
        self.win = main_window                            # 儲存主視窗參照
        self.win.setAcceptDrops(True)                     # 啟用主視窗的拖放接受
        self.win.installEventFilter(self)                 # 安裝事件過濾器（攔截拖放事件）

        # 建立拖拽提示遮罩（疊加在主視窗上方）
        self.overlay = DropOverlay(self.win)              # 實例化遮罩層
        self.overlay.resize(self.win.size())              # 設定尺寸與主視窗一致

    # ----- 事件過濾器：攔截拖放與視窗尺寸變化 ----------------------------------------
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self.win:                           # 僅處理主視窗的事件
            evt_type = event.type()                       # 取得事件類型

            # 拖入事件（游標進入主視窗且攜帶有效數據）
            if evt_type == QEvent.Type.DragEnter:
                if event.mimeData().hasUrls() or event.mimeData().hasText():
                    event.acceptProposedAction()          # 接受拖放動作
                    self.overlay.resize(self.win.size())  # 確保遮罩尺寸同步
                    self.overlay.setWindowOpacity(0.85)   # 設定半透明可見
                    self.overlay.show()                   # 顯示提示遮罩
                    self.overlay.raise_()                 # 置頂於所有子組件上方
                    return True

            # 拖離事件（游標移出主視窗）
            elif evt_type == QEvent.Type.DragLeave:
                self.overlay.hide()                       # 立即隱藏遮罩（不留殘影）
                return True

            # 放下事件（使用者放開滑鼠按鍵）
            elif evt_type == QEvent.Type.Drop:
                self.overlay.hide()                       # 隱藏遮罩
                self._handle_drop(event)                  # 處理實際的拖放數據
                return True

            # 視窗縮放事件（確保遮罩跟隨調整）
            elif evt_type == QEvent.Type.Resize:
                if self.overlay.isVisible():              # 若遮罩正在顯示
                    self.overlay.resize(self.win.size())  # 同步調整大小

        return super().eventFilter(watched, event)       # 其他事件交由父類處理

    # ----- 解析拖放數據（從 MIME 中提取檔案或文字）-----------------------------------
    def _handle_drop(self, event: QDropEvent):
        """解析拖放數據（檔案路徑或 URL）"""
        mime = event.mimeData()                           # 取得 MIME 數據物件
        print("📥 [DropManager] 檢測到 Drop 事件！開始解析數據...")

        # 處理檔案列表（多個檔案拖放）
        if mime.hasUrls():
            for qurl in mime.urls():                      # 遍歷每一個 URL
                file_path = qurl.toLocalFile()            # 轉為本地路徑（若為網路 URL 則為空）
                if file_path:
                    print(f"📄 [DropManager] 讀取本地檔案: {file_path}")
                    self.process_file(file_path)          # 處理本地檔案
                else:
                    raw_url = qurl.toString()             # 取出原始網址字串
                    print(f"🌐 [DropManager] 讀取網路 URL: {raw_url}")
                    self.process_url(raw_url)             # 處理網路 URL
            event.acceptProposedAction()                  # 確認事件已被處理

        # 處理純文字拖放（可能是網址或 M3U 連結）
        elif mime.hasText():
            text = mime.text().strip()                    # 取得文字並去除前後空白
            print(f"🔤 [DropManager] 讀取拖入文字: {text}")
            if text.startswith("http://") or text.startswith("https://"):
                self.process_url(text)                    # 若為網址則呼叫 URL 處理
            event.acceptProposedAction()

    # ----- 檔案路徑分流（根據副檔名決定動作）-----------------------------------------
    def process_file(self, file_path: str):
        """核心分流邏輯：根據副檔名決定播放、加載字幕或解析 M3U"""
        ext = os.path.splitext(file_path)[1].lower()      # 取得小寫副檔名

        # 若為播放清單（.m3u / .m3u8）
        if ext in self.PLAYLIST_EXTS:
            print(f"📦 [DropManager] 傳送 M3U 至 start_parse_m3u(): {file_path}")
            self.win.start_parse_m3u(file_path)           # 呼叫主視窗解析 M3U

        # 若為字幕檔案
        elif ext in self.SUB_EXTS:
            self._load_subtitle(file_path)                # 加載字幕至當前播放器

        # 其餘視為一般媒體檔案
        else:
            self._play_media(file_path)                   # 播放媒體

            # 紀錄至本地媒體播放清單（僅取檔名）
            file_name = os.path.basename(file_path)       # 提取純檔名
            # 自動加入歷史紀錄並切換至「本地媒體」視圖
            self.win.channel_mgr.add_local_media_record(file_name, file_path)

    # ----- 網路 URL 分流（判斷是否為 M3U 清單）----------------------------------------
    def process_url(self, url: str):
        """網路 URL 分流：若為 M3U 網址則解析，否則直接播放"""
        if url.endswith(".m3u") or url.endswith(".m3u8") or "m3u" in url.lower():
            print(f"🌐 [DropManager] 傳送 URL 至 start_parse_m3u(): {url}")
            self.win.start_parse_m3u(url)                 # 解析網路 M3U
        else:
            self._play_media(url)                         # 直接播放該網址（串流）

    # ----- 實際播放媒體（對接當前焦點的播放器）----------------------------------------
    def _play_media(self, path_or_url: str):
        """對接真實的 video_widget.play() 方法（自動定位當前分屏）"""
        active_idx = self.win.active_player_index         # 取得當前活躍分屏索引
        screen_mgr = self.win.screen_mgr                  # 取得螢幕管理器

        target_widget = None                              # 目標播放器變數

        # 優先從 video_widgets 列表中取得對應索引的組件
        if screen_mgr:
            target_widget = self.win.video_widgets[active_idx]

        # 備援方案：若無法取得，則使用主視窗的預設 video_widget
        if not target_widget:
            target_widget = self.win.video_widget

        # 執行播放
        if target_widget and hasattr(target_widget, 'play'):
            print(f"▶️ [DropManager] 成功調用 target_widget.play(): {path_or_url}")
            target_widget.play(path_or_url)               # 播放媒體
        else:
            print(f"❌ [DropManager] 錯誤：無法定位具備 play() 方法的視窗組件！")

    # ----- 載入外掛字幕（自動附加至當前播放器）----------------------------------------
    def _load_subtitle(self, sub_path: str):
        """載入外掛字幕（透過 mpv 的 sub-add 指令）"""
        active_idx = self.win.active_player_index
        screen_mgr = self.win.screen_mgr
        player = None

        # 嘗試從螢幕管理器取得對應的播放器實例
        if screen_mgr and hasattr(screen_mgr, 'get_player'):
            player = screen_mgr.get_player(active_idx)
        elif hasattr(self.win, 'video_widget'):
            player = self.win.video_widget                # 使用預設播放器

        # 若取得播放器且具有 command 方法（mpv 核心）
        if player and hasattr(player, 'command'):
            print(f"💬 [DropManager] 載入字幕: {sub_path}")
            player.command("sub-add", sub_path)           # 透過 mpv 命令加載字幕

    # ----- 開啟本地檔案對話框（Ctrl+O 快捷鍵）----------------------------------------
    def open_file_dialog(self):
        """Ctrl+O 本地檔案對話框（支援影音、字幕、播放清單）"""
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
        if file_path:                                     # 若使用者選擇了檔案
            self.process_file(file_path)                  # 交由統一處理流程
