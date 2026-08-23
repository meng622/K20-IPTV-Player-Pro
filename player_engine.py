# player_engine.py
from config import *
from config import _script_dir
from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication
import ctypes
from ctypes import wintypes # [關鍵修復] 補上 s (wintypes)

# ==================== libmpv ctypes 封裝 ====================
if getattr(sys, 'frozen', False):
    _base_path = sys._MEIPASS
else:
    _base_path = _script_dir

_libmpv_path = os.path.join(_base_path, "libmpv-2.dll")
# ============================================================

WM_LBUTTONDBLCLK = 0x0203
WM_MOUSEMOVE = 0x0200

from PyQt6 import sip  # 務必確保在檔案頂部或此處導入 sip 用於檢查 C++ 物件存活狀態

class MpvEventFilter(QObject):
    """安全版的 Qt 事件監聽器：增加 sip 檢查防範 RuntimeError"""
    def __init__(self, target_widget):
        super().__init__()
        self.target_widget = target_widget

    def eventFilter(self, obj, event):
        # [關鍵修復 1] 防護：檢查 target_widget 的 C++ 底層物件是否已被 C++ 釋放
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
            except RuntimeError:
                pass
        return super().eventFilter(obj, event)

class LoadingSpinner(QWidget):
    # 轉圈圖示
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedSize(160, 160)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)

    def _rotate(self):
        self._angle = (self._angle + 30) % 360
        self.update()
        

    def start(self):
        self.show()
        self._timer.start(50)

    def stop(self):
        self._timer.stop()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(5, 5, -5, -5)
        pen = QPen(QColor(255, 255, 255, 200), 4)
        painter.setPen(pen)
        painter.drawArc(rect, -self._angle * 16, 280 * 16)


class EventOverlay(QWidget):
    """終極怪招：利用 ToolTip 視窗屬性搶奪最高 Z-Order 置頂轉圈圈"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # ToolTip 屬性在 Windows 底層擁有極高繪製優先級，mpv 絕對蓋不住
        self.setWindowFlags(
            Qt.WindowType.ToolTip | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.spinner = LoadingSpinner(self)
        layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignCenter)
        self.spinner.hide()

    def paintEvent(self, event):
        if self.spinner.isVisible():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # 畫半透明黑底
            painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

    def start_loading(self):
        if self.parentWidget():
            # 強制更新視窗座標到螢幕全域位置
            p = self.parentWidget()
            global_pos = p.mapToGlobal(p.rect().topLeft())
            self.setGeometry(global_pos.x(), global_pos.y(), p.width(), p.height())
            
        self.spinner.start()
        self.show()
        self.raise_()
        self.update()

    def stop_loading(self):
        self.spinner.stop()
        self.hide()
        self.update()
        self.spinner.stop()
        self.hide()
        self.update()


class MpvEmbedWidget(QWidget):
    requestFullscreenToggle = pyqtSignal()
    requestShowControls = pyqtSignal()
    errorOccurred = pyqtSignal(str)          
    channelTimeout = pyqtSignal(str)         

    MPV_FORMAT_DOUBLE = 5
    MPV_FORMAT_STRING = 1

    def __init__(self, parent=None):
        super().__init__(parent)
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
        
        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.timeout.connect(self._check_channel_alive)
        self._current_url = ""

        self._setup_api()

        # 1. 建立純粹負責 Spinner 的 Overlay
        self._overlay = EventOverlay(self)
        self._overlay.setGeometry(self.rect())

        # 2. 安全安裝 Qt 層級事件過濾器
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
            self._set_option("osd-level", "1")
            self._set_option("force-window", "immediate")
            self._set_option("keep-open", "yes")
            self._set_option("sub-auto", "fuzzy")

            self._set_option("demuxer-lavf-o", "reconnect=1,reconnect_streamed=1,reconnect_delay_max=5")
            self._set_option("network-timeout", "10")

            if self.hw_enabled:
                self._set_option("hwdec", "auto-safe")
                self._set_option("gpu-context", "d3d11")
            else:
                self._set_option("hwdec", "no")

            self._set_option("vd-lavc-threads", "2")
            self._set_option("demuxer-max-bytes", "10M")
            self._set_option("wid", wid)

            ret = self._lib.mpv_initialize(self._ctx)
            if ret < 0:
                raise RuntimeError(f"mpv_initialize failed: {ret}")
            
            self._mpv_ready = True
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
        
        # [關鍵修正] 啟動加載轉圈
        self._overlay.start_loading()
        self._show_osd_text("載入串流中...", 6000)
        
        QApplication.processEvents()

        try:
            cmd = f'loadfile "{url}"'.encode('utf-8')
            self._lib.mpv_command_string(self._ctx, cmd)
            QTimer.singleShot(2000, self._enable_subs)
            self._load_timer.start(5000)
            
        except Exception as e:
            print(f"[MpvEngine] 播放指令執行失敗: {e}")
            self._overlay.stop_loading()
            self.errorOccurred.emit(str(e))

    def _check_channel_alive(self):
        if not self._ctx:
            self._overlay.stop_loading()
            return
        
        time_pos = self.get_time_pos()
        duration = self.get_duration()
        idle_state = self.get_property_string("idle-active")
        
        if idle_state == "yes" or (time_pos == 0 and duration == 0):
            print(f"[MpvEngine] 警告：頻道可能已失效或連線逾時 -> {self._current_url}")
            self._show_osd_text("頻道連線逾時 / 已失效", 3000)
            self._overlay.stop_loading()
            self.channelTimeout.emit(self._current_url)
        else:
            self._show_osd_text("", 10)
            self._overlay.stop_loading()

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
            except Exception:
                pass

    def resume(self):
        if self._ctx:
            self._paused = False
            try:
                self._lib.mpv_command_string(self._ctx, b"set pause no")
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
        if self._load_timer.isActive():
            self._load_timer.stop()
        self._show_osd_text("", 10)
        self._overlay.stop_loading()
        if self._ctx:
            try:
                self._lib.mpv_command_string(self._ctx, b"stop")
            except Exception:
                pass

    @property
    def is_paused(self):
        return self._paused

    def get_time_pos(self):
        if not self._ctx:
            return 0
        try:
            val = c_double(0)
            ret = self._lib.mpv_get_property(self._ctx, b"time-pos", self.MPV_FORMAT_DOUBLE, byref(val))
            return val.value if ret >= 0 else 0
        except Exception:
            return 0

    def get_duration(self):
        if not self._ctx:
            return 0
        try:
            val = c_double(0)
            ret = self._lib.mpv_get_property(self._ctx, b"duration", self.MPV_FORMAT_DOUBLE, byref(val))
            return val.value if ret >= 0 else 0
        except Exception:
            return 0

    def screenshot(self, path=None):
        if self._ctx:
            try:
                snapshots_dir = os.path.join(_script_dir, "snapshots")
                os.makedirs(snapshots_dir, exist_ok=True)
                
                # [強制覆寫] 確保絕對不會掉到外面去
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
        if hasattr(self, '_overlay') and self._overlay and self._overlay.isVisible():
            global_pos = self.mapToGlobal(self.rect().topLeft())
            self._overlay.setGeometry(global_pos.x(), global_pos.y(), self.width(), self.height())

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, '_overlay') and self._overlay and self._overlay.isVisible():
            global_pos = self.mapToGlobal(self.rect().topLeft())
            self._overlay.setGeometry(global_pos.x(), global_pos.y(), self.width(), self.height())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._ctx:
            QTimer.singleShot(100, self._init_mpv)

    def closeEvent(self, event):
        if self._load_timer.isActive():
            self._load_timer.stop()
        if self._ctx:
            try:
                self._lib.mpv_terminate_destroy(self._ctx)
            except Exception:
                pass
            self._ctx = None
        super().closeEvent(event)