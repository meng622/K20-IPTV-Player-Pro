# [代碼起點]
from config import *  # 匯入配置
from PyQt6 import sip  # sip 套件
from config import _script_dir  # 腳本目錄
from ctypes import wintypes  # 視窗類型

# ========== 核心檔案搜尋（本地 / libs / D:\Libs 都支援） ==========
CORE_FILES = ("libmpv-2.dll", "ffmpeg.exe", "yt-dlp.exe")  # 三大核心


def _build_core_dirs():  # 建立搜尋順序
    dirs = []  # 候選目錄
    if getattr(sys, "frozen", False):  # 打包後優先找 _MEIPASS
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            dirs.append(meipass)
    env_dir = os.environ.get("K20_LIBS", "").strip()  # 可選的環境變數
    if env_dir:
        dirs.append(env_dir)
    dirs.append(_script_dir)  # main.py / exe 同目錄
    dirs.append(os.path.join(_script_dir, "libs"))  # 專案 libs 子目錄
    dirs.append(r"D:\Libs")  # 舊習慣
    result, seen = [], set()  # 去重
    for d in dirs:
        d = os.path.abspath(os.path.expanduser(d))  # 絕對路徑
        key = os.path.normcase(d)  # Windows 不分大小寫
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result


def _find_core(name):  # 找單一核心檔案
    for d in _core_dirs:
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return path
    return ""  # 找不到


_core_dirs = _build_core_dirs()  # 搜尋順序
_libmpv_path = _find_core("libmpv-2.dll")  # libmpv
_ffmpeg_path = _find_core("ffmpeg.exe")  # ffmpeg
_ytdl_path = _find_core("yt-dlp.exe")  # yt-dlp
_libmpv_dir = os.path.dirname(_libmpv_path) if _libmpv_path else ""  # libmpv 目錄
_ffmpeg_dir = os.path.dirname(_ffmpeg_path) if _ffmpeg_path else _core_dirs[0]  # ffmpeg 目錄
if not _ytdl_path:  # 找不到時仍給一個候選路徑
    _ytdl_path = os.path.join(_core_dirs[0], "yt-dlp.exe")

for _d in {_libmpv_dir, _ffmpeg_dir, os.path.dirname(_ytdl_path)}:  # 加入 DLL/PATH
    if not _d:
        continue
    if _d not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")
    try:
        os.add_dll_directory(_d)  # 讓 libmpv 找到同目錄依賴
    except (OSError, AttributeError):
        pass
# ============================================

WM_LBUTTONDBLCLK = 0x0203  # 雙擊代碼
WM_MOUSEMOVE = 0x0200  # 移動代碼

class MpvEmbedWidget(QWidget):  # 播放核心
    requestFullscreenToggle = pyqtSignal()  # 全屏信號
    requestShowControls = pyqtSignal()  # 顯控信號
    errorOccurred = pyqtSignal(str)  # 報錯信號
    channelTimeout = pyqtSignal(str)  # 逾時信號
    pauseChanged = pyqtSignal(bool)  # 暫停信號
    
    MPV_FORMAT_DOUBLE = 5  # 浮點格式
    MPV_FORMAT_STRING = 1  # 字串格式

    def __init__(self, parent=None, cache_mb=100):  # 初始化
        super().__init__(parent)  # 呼叫父類
        self.cache_mb = cache_mb  # 快取大小
        self.initial_volume = 100  # 啟動音量（主視窗會覆寫）
        # 修正：加上 `#` 或選擇器，只讓播放器本體保持黑底，不污染其他子元件
        self.setStyleSheet("VideoWidget { background-color: #000000; }")  # 僅播放器黑底  # 黑色背景
        self.setMouseTracking(True)  # 滑鼠追蹤
        self.mpv = self  # 指向自己
        
        if not _libmpv_path:  # 找不到核心
            raise RuntimeError(
                "找不到 libmpv-2.dll，已搜尋：\n" + "\n".join(_core_dirs)
                + "\n請把 libmpv-2.dll 放到 K20_Pro、K20_Pro\\libs 或 D:\\Libs。"
            )  # 明確提示
        try:  # 嘗試載入
            self._lib = ctypes.CDLL(_libmpv_path)  # 載入 DLL
        except OSError as e:  # 載入失敗
            raise RuntimeError(f"無法載入 {_libmpv_path}: {e}")  # 拋出異常

        self._ctx = None  # 核心指標
        self._paused = False  # 暫停標記
        self._mpv_ready = False  # 就緒標記
        self.hw_enabled = True  # 硬解開關
        self.is_multi_mode = False  # 多屏標記
        
        self._load_timer = QTimer(self)  # 逾時計時
        self._load_timer.setSingleShot(True)  # 單次觸發
        self._load_timer.timeout.connect(self._check_channel_alive)  # 逾時檢查
        self._current_url = ""  # 當前網址
        self._setup_api()  # 設定 API

    # ---------- 以下所有方法保持不變 ----------
    def mouseDoubleClickEvent(self, event):  # 雙擊事件
        if event.button() == Qt.MouseButton.LeftButton:  # 左鍵雙擊
            self.requestFullscreenToggle.emit()  # 發出全屏
            event.accept()  # 接收事件

    def mouseMoveEvent(self, event):  # 移動事件
        self.requestShowControls.emit()  # 發出顯控
        super().mouseMoveEvent(event)  # 呼叫父類

    def _setup_api(self):  # API 綁定
        self._lib.mpv_create.restype = c_void_p  # 創建回傳
        self._lib.mpv_create.argtypes = []  # 創建參數

        self._lib.mpv_set_option_string.argtypes = [c_void_p, c_char_p, c_char_p]  # 選項參數
        self._lib.mpv_set_option_string.restype = c_int  # 選項回傳

        self._lib.mpv_initialize.argtypes = [c_void_p]  # 初始化參
        self._lib.mpv_initialize.restype = c_int  # 初始化回

        self._lib.mpv_command_string.argtypes = [c_void_p, c_char_p]  # 指令參數
        self._lib.mpv_command_string.restype = c_int  # 指令回傳

        self._lib.mpv_get_property.argtypes = [c_void_p, c_char_p, c_int, ctypes.c_void_p]  # 讀屬性參
        self._lib.mpv_get_property.restype = c_int  # 讀屬性回

        self._lib.mpv_set_property.argtypes = [c_void_p, c_char_p, c_int, ctypes.c_void_p]  # 設屬性參
        self._lib.mpv_set_property.restype = c_int  # 設屬性回

        self._lib.mpv_set_property_string.argtypes = [c_void_p, c_char_p, c_char_p]  # 設字串參
        self._lib.mpv_set_property_string.restype = c_int  # 設字串回

        self._lib.mpv_terminate_destroy.argtypes = [c_void_p]  # 銷毀參數
        self._lib.mpv_terminate_destroy.restype = None  # 銷毀回傳

        self._lib.mpv_free.argtypes = [c_void_p]  # 釋放參數
        self._lib.mpv_free.restype = None  # 釋放回傳

    def _set_property_string(self, name, value):  # 設字串屬
        if self._ctx:  # 核心存在
            try:  # 嘗試設定
                self._lib.mpv_set_property_string(self._ctx, name.encode('utf-8'), value.encode('utf-8'))  # 設定屬性
            except Exception as e:  # 捕捉異常
                print(f"[MpvEngine] 設定屬性 {name} 失敗: {e}")  # 印錯誤訊

    def _init_mpv(self):  # 啟動核心
        if self._ctx:  # 已初始化
            return  # 結束執行

        try:  # 嘗試初始化
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)  # 繪製優化
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)  # 無背優化

            self._ctx = self._lib.mpv_create()  # 創建核心
            if not self._ctx:  # 創建失敗
                raise RuntimeError("mpv_create failed")  # 拋出異常

            wid = str(int(self.winId()))  # 視窗代碼

            self._set_option("input-default-bindings", "no")  # 關預設鍵
            self._set_option("input-vo-keyboard", "no")  # 關視窗鍵
            self._set_option("osc", "no")  # 關介面
            self._set_option("osd-level", "0")  # 關提示
            self._set_option("force-window", "immediate")  # 強制視窗
            self._set_option("keep-open", "yes")  # 保持開啟
            self._set_option("sub-auto", "fuzzy")  # 字幕模糊

            self._set_option("demuxer-lavf-o", "reconnect=1,reconnect_streamed=1,reconnect_delay_max=5")  # 重連參數
            self._set_option("network-timeout", "10")  # 網路逾時

            if self.hw_enabled and not self.is_multi_mode:  # 硬解條件
                self._set_option("hwdec", "auto-safe")  # 安全硬解
                self._set_option("gpu-context", "d3d11")  # GPU 上下
            else:  # 軟解條件
                self._set_option("hwdec", "no")  # 關閉硬解

            # 記憶體極限優化
            self._set_option("cache", "yes")  # 開啟快取
            self._set_option("demuxer-readahead-secs", "2")  # 預讀秒數
            
            try:  # 使用者設定的緩衝大小
                limit_mb = int(self.cache_mb)  # 轉整數
            except (TypeError, ValueError):  # 設定值異常
                limit_mb = 100  # 預設
            limit_mb = max(10, min(limit_mb, 500))  # 限制範圍
            if self.is_multi_mode:  # 多屏省記憶體
                limit_mb = min(limit_mb, 15)  # 上限 15MB
            cache_secs = max(5, min(30, limit_mb // 10))  # MB 越大，可緩衝秒數越多
            self._set_option("cache-secs", str(cache_secs))  # 快取秒數
            self._set_option("demuxer-max-bytes", f"{limit_mb}M")  # 緩衝上限
            self._set_option("demuxer-max-back-bytes", "0M")  # 後退快取
            self._set_option("demuxer-seekable-cache", "no")  # 尋航快取
            
            self._set_option("vd-lavc-threads", "1")  # 解碼線程
            self._set_option("gpu-shader-cache", "no")  # 着色快取
            self._set_option("scale", "bilinear")  # 採樣演算法
            self._set_option("override-display-fps", "30")  # 鎖定幀率
            
            self._set_option("cache-pause", "no")  # 暫停快取
            self._set_option("cache-pause-initial", "yes")  # 首載暫停
            
            self._set_option("ytdl", "yes")  # YT解析

            self._set_option("ytdl-format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best")  # 畫質優先
            # ytdl_hook 的選項必須用「腳本名-選項名」格式，否則會被忽略
            self._set_option("script-opts", f"ytdl_hook-ytdl_path={_ytdl_path}")  # yt-dlp 絕對路徑
            
            # 將共用目錄加入 PATH 環境變數，以便 mpv 找到 ffmpeg
            if _ffmpeg_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
            
            self._set_option("wid", wid)  # 綁定視窗

            ret = self._lib.mpv_initialize(self._ctx)  # 啟動核心
            if ret < 0:  # 啟動失敗
                raise RuntimeError(f"mpv_initialize failed: {ret}")  # 拋出異常
            
            self._mpv_ready = True  # 標記就緒
            self.set_volume(self.initial_volume)  # 套用上次音量
            
        except Exception as e:  # 捕捉異常
            print(f"[MpvEngine] 初始化異常: {e}")  # 輸出日誌
            self._ctx = None  # 清空核心
            self._mpv_ready = False  # 清空就緒
            self.errorOccurred.emit(str(e))  # 發出報錯

    def _set_option(self, name, value):  # 設選項值
        if self._ctx:  # 核心存在
            try:  # 嘗試設定
                ret = self._lib.mpv_set_option_string(self._ctx, name.encode('utf-8'), value.encode('utf-8'))  # 設定選項
                if ret < 0:  # 設定警告
                    print(f"Warning: mpv option {name}={value} failed: {ret}")  # 輸出警告
            except Exception as e:  # 捕捉異常
                print(f"[MpvEngine] _set_option 異常: {e}")  # 輸出日誌

    def _show_osd_text(self, text, duration_ms=3000):  # OSD 提示
        if self._ctx:  # 核心存在
            try:  # 嘗試顯示
                cmd = f'show-text "{text}" {duration_ms}'.encode('utf-8')  # 文字指令
                self._lib.mpv_command_string(self._ctx, cmd)  # 送出指令
            except Exception as e:  # 捕捉異常
                print(f"[MpvEngine] 顯示 OSD 失敗: {e}")  # 輸出日誌

    def play(self, url):  # 開始播放
        if not url or not isinstance(url, str):  # 網址無效
            print("[MpvEngine] 錯誤：嘗試播放無效或空白的 URL")  # 輸出錯誤
            return  # 結束執行

        if not self._ctx:  # 核心未開
            self._init_mpv()  # 初始化它
        if not self._ctx:  # 初始化失
            return  # 結束執行

        self._paused = False  # 清空暫停
        self._current_url = url  # 記當前網
        self._set_property_string("vid", "auto")  # 還原影像軌（stop 會設 0）
        self._show_osd_text("載入串流中...", 6000)  # 提示載入

        try:  # 嘗試載入
            cmd = f'loadfile "{url}"'.encode('utf-8')  # 載檔指令
            self._lib.mpv_command_string(self._ctx, cmd)  # 送出指令
            QTimer.singleShot(2000, self._enable_subs)  # 延遲字幕

            is_yt = "youtube.com" in url.lower() or "youtu.be" in url.lower()  # 判斷 YT
            timeout_ms = 12000 if is_yt else 5000  # 逾時毫秒
            self._load_timer.start(timeout_ms)  # 啟動計時

            self._set_property_string("pause", "no")  # 開始播放
        except Exception as e:  # 捕捉異常
            print(f"[MpvEngine] 播放指令執行失敗: {e}")  # 輸出日誌
            self.errorOccurred.emit(str(e))  # 發出報錯

    def _check_channel_alive(self):  # 檢查連線
        if not self._ctx:  # 核心未開
            return  # 結束執行
        
        time_pos = self.get_time_pos()  # 取得時間
        duration = self.get_duration()  # 取得片長
        idle_state = self.get_property_string("idle-active")  # 閒置狀態
        
        if idle_state == "yes" or (time_pos == 0 and duration == 0):  # 失效條件
            print(f"[MpvEngine] 警告：頻道可能已失效或連線逾時 -> {self._current_url}")  # 輸出警告
            self._show_osd_text("頻道連線逾時 / 已失效", 3000)  # 顯示逾時
            self.channelTimeout.emit(self._current_url)  # 發出逾時
        else:  # 正常播放
            self._show_osd_text("", 10)  # 清除提示
            
            if "youtube.com" in self._current_url.lower() or "youtu.be" in self._current_url.lower():  # YT 標題
                real_title = self.get_media_title()  # 取得標題
                if real_title:  # 標題存在
                    parent_win = self.window()  # 取得主窗
                    parent_win.update_header_title(custom_title=f"[YouTube] - {real_title}")  # 更新標題

    def _enable_subs(self):  # 開啟字幕
        if self._ctx and self._mpv_ready:  # 核心就緒
            try:  # 嘗試啟用
                self._set_property_string("sid", "1")  # 選第一軌
                self._set_property_string("sub-visibility", "yes")  # 顯示字幕
            except Exception:  # 忽略錯誤
                pass  # 跳過不處理

    def pause(self):  # 暫停播放
        if self._ctx:  # 核心存在
            self._paused = True  # 標記暫停
            try:  # 嘗試暫停
                self._lib.mpv_command_string(self._ctx, b"set pause yes")  # 送出暫停
                self.pauseChanged.emit(True)  # 發出暫停
            except Exception:  # 忽略錯誤
                pass  # 跳過不處理

    def resume(self):  # 恢復播放
        if self._ctx:  # 核心存在
            self._paused = False  # 清空暫停
            try:  # 嘗試恢復
                self._lib.mpv_command_string(self._ctx, b"set pause no")  # 送出恢復
                self.pauseChanged.emit(False)  # 發出恢復
            except Exception:  # 忽略錯誤
                pass  # 跳過不處理

    def set_volume(self, vol):  # 設定音量
        if self._ctx:  # 核心存在
            try:  # 嘗試設定
                val = ctypes.c_double(vol)  # 轉浮點數
                self._lib.mpv_set_property(self._ctx, b"volume", self.MPV_FORMAT_DOUBLE, ctypes.byref(val))  # 設定音量
            except Exception as e:  # 捕捉異常
                print(f"[MpvEngine] 設定音量失敗: {e}")  # 輸出日誌
            
    def set_mute(self, mute: bool):  # 設定靜音
        if self._ctx:  # 核心存在
            val = "yes" if mute else "no"  # 布林轉換
            self._set_property_string("mute", val)  # 設定靜音

    def get_mute(self) -> bool:  # 讀取靜音
        if not self._ctx:  # 核心未開
            return False  # 預設不靜
        val = self.get_property_string("mute")  # 取得靜音
        return val == "yes"  # 回傳布林

    def get_volume(self) -> float:  # 讀取音量
        if not self._ctx:  # 核心未開
            return 100.0  # 預設滿音
        try:  # 嘗試讀取
            val = ctypes.c_double(100.0)  # 預設變數
            ret = self._lib.mpv_get_property(self._ctx, b"volume", self.MPV_FORMAT_DOUBLE, ctypes.byref(val))  # 取得音量
            return val.value if ret >= 0 else 100.0  # 回傳音量
        except Exception:  # 讀取失敗
            return 100.0  # 預設滿音

    def stop(self):  # 停止播放
        print("[MpvEngine] stop() 被調用")  # 輸出日誌
        self._load_timer.stop()  # 停止計時
        self._show_osd_text("", 10)  # 清除提示
        if self._ctx:  # 核心存在
            try:  # 嘗試停止
                self._lib.mpv_command_string(self._ctx, b"stop")  # 停止播放
                self._lib.mpv_command_string(self._ctx, b"set vid 0")  # 強制黑屏
            except Exception as e:  # 捕捉異常
                print(f"[MpvEngine] stop 命令失敗: {e}")  # 輸出日誌

    def clear_media(self):  # 完全清空這個分屏
        self.stop()  # 停止播放
        self._current_url = ""  # 清歷史網址
        self.channel_url = ""  # 清頻道網址
        self.channel_name = ""  # 清頻道名稱
        self.channel_info = {}  # 清頻道資訊
        self.has_media = False  # 標記無媒體
        self.update()  # 刷新黑屏

    @property  # 屬性裝飾
    def is_paused(self):  # 是否暫停
        return self._paused  # 回傳暫停

    def get_time_pos(self):  # 取得進度
        if not self._ctx:  # 核心未開
            return 0  # 回傳歸零
        try:  # 嘗試讀取
            val = ctypes.c_double(0)  # 預設變數
            ret = self._lib.mpv_get_property(self._ctx, b"time-pos", self.MPV_FORMAT_DOUBLE, ctypes.byref(val))  # 讀取秒數
            return val.value if ret >= 0 else 0  # 回傳秒數
        except Exception:  # 讀取失敗
            return 0  # 回傳歸零

    def get_duration(self):  # 取得片長
        if not self._ctx:  # 核心未開
            return 0  # 回傳歸零
        try:  # 嘗試讀取
            val = ctypes.c_double(0)  # 預設變數
            ret = self._lib.mpv_get_property(self._ctx, b"duration", self.MPV_FORMAT_DOUBLE, ctypes.byref(val))  # 讀取總長
            return val.value if ret >= 0 else 0  # 回傳總長
        except Exception:  # 讀取失敗
            return 0  # 回傳歸零

    def get_media_title(self):  # 取得標題
        title = self.get_property_string("media-title")  # 讀取標題
        return title if title else ""  # 回傳標題
    
    def toggle_stats(self):  # 切換統計
        if self._ctx and self._mpv_ready:  # 核心就緒
            try:  # 嘗試切換
                self._lib.mpv_command_string(self._ctx, b"script-binding stats/display-stats-toggle")  # 顯示統計
            except Exception as e:  # 捕捉異常
                print(f"[MpvEngine] 切換 Stats 失敗: {e}")  # 輸出日誌

    def screenshot(self, path=None):  # 畫面截圖
        if self._ctx:  # 核心存在
            try:  # 嘗試截圖
                snapshots_dir = os.path.join(_script_dir, "snapshots")  # 截圖目錄
                os.makedirs(snapshots_dir, exist_ok=True)  # 建資料夾
                
                if path:  # 自訂檔名
                    filename = os.path.basename(path)  # 取得檔名
                else:  # 自動檔名
                    filename = f"snapshot_{time.strftime('%Y%m%d_%H%M%S')}.png"  # 時間檔名
                
                abs_path = os.path.join(snapshots_dir, filename)  # 絕對路徑
                safe_path = abs_path.replace('\\', '/')  # 格式轉換
                
                cmd = f'screenshot-to-file "{safe_path}" video'.encode('utf-8')  # 截圖指令
                self._lib.mpv_command_string(self._ctx, cmd)  # 送出指令
                return True  # 截圖成功
            except Exception as e:  # 捕捉異常
                print(f"[MpvEngine] 截圖失敗: {e}")  # 輸出日誌
        return False  # 截圖失敗
        
    def set_aspect(self, ratio):  # 畫面比例
        if not self._ctx:  # 核心未開
            return  # 結束執行
        if ratio in (None, "", "original"):  # 預設比例
            self._set_property_string("keepaspect", "yes")  # 保持原始比例
            self._set_property_string("video-aspect-override", "no")  # 取消覆寫
        elif ratio == "fill":  # 填滿畫面
            self._set_property_string("keepaspect", "no")  # 拉伸填滿
        else:  # 指定比例
            self._set_property_string("keepaspect", "yes")  # 保持比例
            self._set_property_string("video-aspect-override", str(ratio))  # 強制比例

    def get_property_string(self, name):  # 讀字串值
        if not self._ctx:  # 核心未開
            return None  # 回傳無值
        try:  # 嘗試讀取
            ptr = c_char_p()  # 指標變數
            ret = self._lib.mpv_get_property(self._ctx, name.encode('utf-8'), self.MPV_FORMAT_STRING, ctypes.byref(ptr))  # 讀取屬性
            if ret >= 0 and ptr.value:  # 讀取成功
                result = ptr.value.decode('utf-8')  # 解碼字串
                self._lib.mpv_free(ptr)  # 釋放記憶
                return result  # 回傳結果
        except Exception:  # 捕捉異常
            pass  # 跳過不處理
        return None  # 回傳無值

    def command(self, *args):  # 自訂指令
        if self._ctx and args:  # 指令存在
            try:  # 嘗試執行
                cmd_str = " ".join(str(a) for a in args).encode('utf-8')  # 組裝指令
                self._lib.mpv_command_string(self._ctx, cmd_str)  # 送出指令
            except Exception as e:  # 捕捉異常
                print(f"[MpvEngine] 執行自定義指令失敗: {e}")  # 輸出日誌

    def resizeEvent(self, event):  # 縮放事件
        super().resizeEvent(event)  # 呼叫父類

    def moveEvent(self, event):  # 移動事件
        super().moveEvent(event)  # 呼叫父類

    def showEvent(self, event):  # 顯示事件
        super().showEvent(event)  # 呼叫父類
        if not self._ctx:  # 核心未開
            QTimer.singleShot(100, self._init_mpv)  # 延遲啟動

    def closeEvent(self, event):  # 關閉事件
        self._load_timer.stop()  # 停止計時
        if self._ctx:  # 核心存在
            try:  # 嘗試關閉
                self._lib.mpv_terminate_destroy(self._ctx)  # 銷毀核心
            except Exception:  # 忽略錯誤
                pass  # 跳過不處理
            self._ctx = None  # 清空核心
        super().closeEvent(event)  # 呼叫父類
# [代碼終點]