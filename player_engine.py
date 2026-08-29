# player_engine.py
from config import *
from PyQt6 import sip
from config import _script_dir
from ctypes import wintypes

# ==================== libmpv ctypes 封裝 ====================
if getattr(sys, 'frozen', False):
    _base_path = sys._MEIPASS
else:
    _base_path = _script_dir

_libmpv_path = os.path.join(_base_path, "libmpv-2.dll")
# ============================================================

WM_LBUTTONDBLCLK = 0x0203
WM_MOUSEMOVE = 0x0200

class MpvEventFilter(QObject):
    """安全版的 Qt 事件監聽器：增加 sip 檢查防範 RuntimeError"""
    def __init__(self, target_widget):
        super().__init__()
        self.target_widget = target_widget

    def eventFilter(self, obj, event):
        if not self.target_widget or sip.isdeleted(self.target_widget):
            return False
        if isinstance(obj, QWidget):
            try:
                if self.target_widget.isAncestorOf(obj) or obj == self.target_widget:
                    if event.type() == QEvent.Type.MouseButtonDblClick:
                        self.target_widget.requestFullscreenToggle.emit()
                        return True
                    elif event.type() == QEvent.Type.MouseMove:
                        self.target_widget.requestShowControls.emit()
            except RuntimeError as e:
                print(f"[MpvEventFilter] RuntimeError: {e}")
        return super().eventFilter(obj, event)


class MpvEmbedWidget(QWidget):
    requestFullscreenToggle = pyqtSignal()
    requestShowControls = pyqtSignal()
    errorOccurred = pyqtSignal(str)          
    channelTimeout = pyqtSignal(str)
    pauseChanged = pyqtSignal(bool)
    
    MPV_FORMAT_DOUBLE = 5
    MPV_FORMAT_STRING = 1

    def __init__(self, parent=None, cache_mb=100):
        super().__init__(parent)
        self.cache_mb = cache_mb  # 儲存緩存設定
        self.setStyleSheet("background-color: #000000;")
        self.setMouseTracking(True)
        
        try:
            self._lib = ctypes.CDLL(_libmpv_path)
        except OSError as e:
            raise RuntimeError(f"無法載入 libmpv-2.dll: {e}\n請確保 libmpv-2.dll 與腳本在同一目錄。")

        self._ctx = None
        self._paused = False
        self._mpv_ready = False
        self.hw_enabled = True
        self.is_multi_mode = False
        
        # 僅保留超時計時器（用於顯示連線逾時）
        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.timeout.connect(self._check_channel_alive)
        self._current_url = ""
        self._setup_api()

        # 安全安裝 Qt 層級事件過濾器
        self._event_filter = MpvEventFilter(self)
        QCoreApplication.instance().installEventFilter(self._event_filter)

    def _setup_api(self):
        self._lib.mpv_create.restype = c_void_p
        self._lib.mpv_create.argtypes = []

        self._lib.mpv_set_option_string.argtypes = [c_void_p, c_char_p, c_char_p]
        self._lib.mpv_set_option_string.restype = c_int

        self._lib.mpv_initialize.argtypes = [c_void_p]
        self._lib.mpv_initialize.restype = c_int

        self._lib.mpv_command_string.argtypes = [c_void_p, c_char_p]
        self._lib.mpv_command_string.restype = c_int

        self._lib.mpv_get_property.argtypes = [c_void_p, c_char_p, c_int, ctypes.c_void_p]
        self._lib.mpv_get_property.restype = c_int

        self._lib.mpv_set_property.argtypes = [c_void_p, c_char_p, c_int, ctypes.c_void_p]
        self._lib.mpv_set_property.restype = c_int

        self._lib.mpv_set_property_string.argtypes = [c_void_p, c_char_p, c_char_p]
        self._lib.mpv_set_property_string.restype = c_int

        self._lib.mpv_terminate_destroy.argtypes = [c_void_p]
        self._lib.mpv_terminate_destroy.restype = None

        self._lib.mpv_free.argtypes = [c_void_p]
        self._lib.mpv_free.restype = None

    def _set_property_string(self, name, value):
        if self._ctx:
            try:
                self._lib.mpv_set_property_string(self._ctx, name.encode('utf-8'), value.encode('utf-8'))
            except Exception as e:
                print(f"[MpvEngine] 設定屬性 {name} 失敗: {e}")

    def _init_mpv(self):
        if self._ctx:
            return

        try:
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

            self._ctx = self._lib.mpv_create()
            if not self._ctx:
                raise RuntimeError("mpv_create failed")

            wid = str(int(self.winId()))

            self._set_option("input-default-bindings", "no")
            self._set_option("input-vo-keyboard", "no")
            self._set_option("osc", "no")
            self._set_option("osd-level", "0")
            self._set_option("force-window", "immediate")
            self._set_option("keep-open", "yes")
            self._set_option("sub-auto", "fuzzy")

            self._set_option("demuxer-lavf-o", "reconnect=1,reconnect_streamed=1,reconnect_delay_max=5")
            self._set_option("network-timeout", "10")

            if self.hw_enabled and not self.is_multi_mode:
                self._set_option("hwdec", "auto-safe")
                self._set_option("gpu-context", "d3d11")
            else:
                self._set_option("hwdec", "no")

            # ===== 直播 / 點播 最大化緩存設定 =====
            cache_size_mb = getattr(self, 'cache_mb', 100)
            
            # 1. 基本開關
            self._set_option("cache", "yes")
            
            # 2. 核心：設定緩存時間（秒）
            cache_secs = 120   # 預設 2 分鐘
            if cache_size_mb >= 500:
                cache_secs = 300   # 5 分鐘
            elif cache_size_mb >= 200:
                cache_secs = 180   # 3 分鐘
            self._set_option("cache-secs", str(cache_secs))
            
            # 3. 向後緩存（讓你拉回更早時間）
            self._set_option("demuxer-max-back-bytes", f"{cache_size_mb * 2}M")
            
            # 4. demuxer 預讀秒數
            self._set_option("demuxer-readahead-secs", "15")
            
            # 5. 允許 seek
            self._set_option("demuxer-seekable-cache", "yes")
            
            # 6. 緩存行為優化
            self._set_option("cache-pause", "no")
            self._set_option("cache-pause-initial", "yes")
            
            # 7. demuxer 緩衝上限（元數據清單）
            self._set_option("demuxer-max-bytes", f"{cache_size_mb * 4}M")
            
            # 8. 確認設定
            cache_secs_value = self.get_property_string("cache-secs")
            print(f"[MpvEngine] 當前 cache-secs 設定：{cache_secs_value} 秒")
            
            self._set_option("vd-lavc-threads", "2")
            
            self._set_option("ytdl", "yes")
            self._set_option("ytdl-format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best")
            _ytdl_path = os.path.join(_base_path, 'yt-dlp.exe').replace('\\', '/')
            _ffmpeg_dir = _base_path.replace('\\', '/')
            self._set_option("script-opts", f"ytdl_path={_ytdl_path},ytdl-ffmpeg-location={_ffmpeg_dir}")
            
            if _ffmpeg_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
            
            self._set_option("wid", wid)

            ret = self._lib.mpv_initialize(self._ctx)
            if ret < 0:
                raise RuntimeError(f"mpv_initialize failed: {ret}")
            
            self._mpv_ready = True
            
            # 打印當前 cache-size 設定值（用於確認）
            cache_size_value = self.get_property_string("cache-size")
            print(f"[MpvEngine] 當前 cache-size 設定: {cache_size_value}")
            
        except Exception as e:
            print(f"[MpvEngine] 初始化異常: {e}")
            self._ctx = None
            self._mpv_ready = False
            self.errorOccurred.emit(str(e))

    def _set_option(self, name, value):
        if self._ctx:
            try:
                ret = self._lib.mpv_set_option_string(self._ctx, name.encode('utf-8'), value.encode('utf-8'))
                if ret < 0:
                    print(f"Warning: mpv option {name}={value} failed: {ret}")
            except Exception as e:
                print(f"[MpvEngine] _set_option 異常: {e}")

    def _show_osd_text(self, text, duration_ms=3000):
        if self._ctx:
            try:
                cmd = f'show-text "{text}" {duration_ms}'.encode('utf-8')
                self._lib.mpv_command_string(self._ctx, cmd)
            except Exception as e:
                print(f"[MpvEngine] 顯示 OSD 失敗: {e}")

    def play(self, url):
        if not url or not isinstance(url, str):
            print("[MpvEngine] 錯誤：嘗試播放無效或空白的 URL")
            return

        if not self._ctx:
            self._init_mpv()
        if not self._ctx:
            return

        self._paused = False
        self._current_url = url
        self._show_osd_text("載入串流中...", 6000)
        QApplication.processEvents()

        try:
            cmd = f'loadfile "{url}"'.encode('utf-8')
            self._lib.mpv_command_string(self._ctx, cmd)
            QTimer.singleShot(2000, self._enable_subs)

            is_yt = "youtube.com" in url.lower() or "youtu.be" in url.lower()
            timeout_ms = 12000 if is_yt else 5000
            self._load_timer.start(timeout_ms)

            self._set_property_string("pause", "no")
        except Exception as e:
            print(f"[MpvEngine] 播放指令執行失敗: {e}")
            self.errorOccurred.emit(str(e))

    def _check_channel_alive(self):
        if not self._ctx:
            return
        
        time_pos = self.get_time_pos()
        duration = self.get_duration()
        idle_state = self.get_property_string("idle-active")
        
        if idle_state == "yes" or (time_pos == 0 and duration == 0):
            print(f"[MpvEngine] 警告：頻道可能已失效或連線逾時 -> {self._current_url}")
            self._show_osd_text("頻道連線逾時 / 已失效", 3000)
            self.channelTimeout.emit(self._current_url)
        else:
            self._show_osd_text("", 10)
            
            # YouTube 自動更新標題
            if "youtube.com" in self._current_url.lower() or "youtu.be" in self._current_url.lower():
                real_title = self.get_media_title()
                if real_title:
                    parent_win = self.window()
                    parent_win.update_header_title(custom_title=f"[YouTube] - {real_title}")

    def _enable_subs(self):
        if self._ctx and self._mpv_ready:
            try:
                self._set_property_string("sid", "1")
                self._set_property_string("sub-visibility", "yes")
            except Exception:
                pass

    def pause(self):
        if self._ctx:
            self._paused = True
            try:
                self._lib.mpv_command_string(self._ctx, b"set pause yes")
                self.pauseChanged.emit(True)
            except Exception:
                pass

    def resume(self):
        if self._ctx:
            self._paused = False
            try:
                self._lib.mpv_command_string(self._ctx, b"set pause no")
                self.pauseChanged.emit(False)
            except Exception:
                pass

    def set_volume(self, vol):
        if self._ctx:
            try:
                val = ctypes.c_double(vol)
                self._lib.mpv_set_property(self._ctx, b"volume", self.MPV_FORMAT_DOUBLE, ctypes.byref(val))
            except Exception as e:
                print(f"[MpvEngine] 設定音量失敗: {e}")
            
    def set_mute(self, mute: bool):
        if self._ctx:
            val = "yes" if mute else "no"
            self._set_property_string("mute", val)

    def get_mute(self) -> bool:
        if not self._ctx:
            return False
        val = self.get_property_string("mute")
        return val == "yes"

    def get_volume(self) -> float:
        if not self._ctx:
            return 100.0
        try:
            val = ctypes.c_double(100.0)
            ret = self._lib.mpv_get_property(self._ctx, b"volume", self.MPV_FORMAT_DOUBLE, ctypes.byref(val))
            return val.value if ret >= 0 else 100.0
        except Exception:
            return 100.0

    def stop(self):
        print("[MpvEngine] stop() 被調用")
        self._load_timer.stop()
        self._show_osd_text("", 10)
        if self._ctx:
            try:
                self._lib.mpv_command_string(self._ctx, b"stop")
                self._lib.mpv_command_string(self._ctx, b"set vid 0")   # 強制變黑
            except Exception as e:
                print(f"[MpvEngine] stop 命令失敗: {e}")

    @property
    def is_paused(self):
        return self._paused

    def get_time_pos(self):
        if not self._ctx:
            return 0
        try:
            val = ctypes.c_double(0)
            ret = self._lib.mpv_get_property(self._ctx, b"time-pos", self.MPV_FORMAT_DOUBLE, ctypes.byref(val))
            return val.value if ret >= 0 else 0
        except Exception:
            return 0

    def get_duration(self):
        if not self._ctx:
            return 0
        try:
            val = ctypes.c_double(0)
            ret = self._lib.mpv_get_property(self._ctx, b"duration", self.MPV_FORMAT_DOUBLE, ctypes.byref(val))
            return val.value if ret >= 0 else 0
        except Exception:
            return 0

    def get_media_title(self):
        title = self.get_property_string("media-title")
        return title if title else ""
    
    def toggle_stats(self):
        if self._ctx and self._mpv_ready:
            try:
                self._lib.mpv_command_string(self._ctx, b"script-binding stats/display-stats-toggle")
            except Exception as e:
                print(f"[MpvEngine] 切換 Stats 失敗: {e}")

    def screenshot(self, path=None):
        if self._ctx:
            try:
                snapshots_dir = os.path.join(_script_dir, "snapshots")
                os.makedirs(snapshots_dir, exist_ok=True)
                
                if path:
                    filename = os.path.basename(path)
                else:
                    filename = f"snapshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
                
                abs_path = os.path.join(snapshots_dir, filename)
                safe_path = abs_path.replace('\\', '/')
                
                cmd = f'screenshot-to-file "{safe_path}" video'.encode('utf-8')
                self._lib.mpv_command_string(self._ctx, cmd)
                return True
            except Exception as e:
                print(f"[MpvEngine] 截圖失敗: {e}")
        return False
        
    def set_aspect(self, ratio):
        if not self._ctx:
            return
        if ratio == "-1" or not ratio:
            self._set_option("video-aspect-override", "-1")
        else:
            self._set_option("video-aspect-override", str(ratio))

    def get_property_string(self, name):
        if not self._ctx:
            return None
        try:
            ptr = c_char_p()
            ret = self._lib.mpv_get_property(self._ctx, name.encode('utf-8'), self.MPV_FORMAT_STRING, ctypes.byref(ptr))
            if ret >= 0 and ptr.value:
                result = ptr.value.decode('utf-8')
                self._lib.mpv_free(ptr)
                return result
        except Exception:
            pass
        return None

    @property
    def mpv(self):
        return self

    def command(self, *args):
        if self._ctx and args:
            try:
                cmd_str = " ".join(str(a) for a in args).encode('utf-8')
                self._lib.mpv_command_string(self._ctx, cmd_str)
            except Exception as e:
                print(f"[MpvEngine] 執行自定義指令失敗: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._ctx:
            QTimer.singleShot(100, self._init_mpv)

    def closeEvent(self, event):
        self._load_timer.stop()
        if self._ctx:
            try:
                self._lib.mpv_terminate_destroy(self._ctx)
            except Exception:
                pass
            self._ctx = None
        super().closeEvent(event)
