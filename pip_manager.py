# [代碼起點]
from config import *  # 匯入配置

class PiPFloatingWindow(QWidget):  # 浮窗類別
    """獨立 PiP 置頂浮窗容器"""

    def __init__(self, pip_mgr):  # 初始化
        super().__init__()  # 呼叫父類
        self.pip_mgr = pip_mgr  # 綁定管家
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )  # 設定視窗
        # 16:9 尺寸限制
        self.PIP_MIN_SIZE = (426, 240)      # 最小尺寸
        self.PIP_DEFAULT_SIZE = (640, 360)  # 預設尺寸
        self.PIP_MAX_SIZE = (854, 480)      # 最大尺寸

        self.setMinimumSize(*self.PIP_MIN_SIZE)  # 設最小限
        self.setMaximumSize(*self.PIP_MAX_SIZE)  # 設最大限
        self.resize(*self.PIP_DEFAULT_SIZE)  # 重設尺寸

        # 佈局設定
        self.layout = QVBoxLayout(self)  # 垂直佈局
        self.layout.setContentsMargins(0, 0, 0, 0)  # 清空邊距
        self.layout.setSpacing(0)  # 清空間距

        # 右上角關閉按鈕
        self.btn_restore = QPushButton("✕", self)  # 還原按鈕
        self.btn_restore.setFixedSize(26, 26)  # 固定尺寸
        self.btn_restore.setToolTip("退出畫中畫並恢復主視窗")  # 懸停提示
        self.btn_restore.setStyleSheet(
            "QPushButton { background: rgba(0,0,0,0.65); color: #ffffff; border: none; font-weight: bold; border-bottom-left-radius: 6px; }"
            "QPushButton:hover { background: #ff4d4f; }"
        )  # 按鈕樣式
        self.btn_restore.clicked.connect(self.pip_mgr.exit_pip)  # 點擊退出

        # 右下角縮放把手
        self.sizegrip = QSizeGrip(self)  # 縮放把手
        self.sizegrip.setFixedSize(16, 16)  # 把手尺寸

        self._drag_pos = None  # 拖曳位置

    def resizeEvent(self, event):  # 縮放事件
        super().resizeEvent(event)  # 呼叫父類
        
        # 防止遞歸
        if getattr(self, '_resizing', False):  # 是否縮放
            return  # 結束執行
        self._resizing = True  # 標記縮放

        # 強制 16:9
        target_w = self.width()  # 當前寬度
        target_h = int(target_w * 9 / 16)  # 計算高度

        # 尺寸限制
        min_w, min_h = getattr(self, 'PIP_MIN_SIZE', (426, 240))  # 讀最小值
        max_w, max_h = getattr(self, 'PIP_MAX_SIZE', (854, 480))  # 讀最大值
        clamped_w = max(min_w, min(target_w, max_w))  # 限制寬度
        clamped_h = max(min_h, min(target_h, max_h))  # 限制高度

        if self.width() != clamped_w or self.height() != clamped_h:  # 需要調整
            self.resize(clamped_w, clamped_h)  # 調整大小

        # 保持位置
        self.btn_restore.move(self.width() - 26, 0)  # 移動按鈕
        self.btn_restore.raise_()  # 置頂按鈕
        self.sizegrip.move(self.width() - 16, self.height() - 16)  # 移動把手
        self.sizegrip.raise_()  # 置頂把手

        self._resizing = False  # 解鎖縮放
        
        self.btn_restore.move(self.width() - 26, 0)  # 移動按鈕
        self.btn_restore.raise_()  # 置頂按鈕
        self.sizegrip.move(self.width() - 16, self.height() - 16)  # 移動把手
        self.sizegrip.raise_()  # 置頂把手

    def showEvent(self, event):  # 顯示事件
        super().showEvent(event)  # 呼叫父類
        self.btn_restore.raise_()  # 置頂按鈕
        self.sizegrip.raise_()  # 置頂把手

    def mousePressEvent(self, event):  # 按下滑鼠
        if event.button() == Qt.MouseButton.LeftButton:  # 左鍵按下
            if not self.btn_restore.geometry().contains(event.pos()) and not self.sizegrip.geometry().contains(event.pos()):  # 點擊空白
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()  # 記偏移量
                event.accept()  # 接收事件

    def mouseMoveEvent(self, event):  # 移動滑鼠
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:  # 拖曳狀態
            self.move(event.globalPosition().toPoint() - self._drag_pos)  # 移動視窗
            event.accept()  # 接收事件

    def mouseReleaseEvent(self, event):  # 放開滑鼠
        self._drag_pos = None  # 清空拖曳

    def mouseDoubleClickEvent(self, event):  # 雙擊滑鼠
        """徹底屏蔽浮窗本體的雙擊"""
        event.accept()  # 屏蔽雙擊


class PiPManager(QObject):  # 管家類別
    """獨立畫中畫 (PiP) 管理器"""

    def __init__(self, main_win):  # 初始化
        super().__init__(main_win)  # 呼叫父類
        self.win = main_win  # 綁定主窗
        self.is_pip_mode = False  # 浮窗狀態
        self.pip_window = None  # 浮窗物件
        self._was_fullscreen = False  # 原全屏態
        self._entering = False  # 正在進入 PiP（避免被誤判為任務欄還原）
        self._restore_timer = QTimer(self)  # 檢查主窗是否被任務欄還原
        self._restore_timer.setInterval(300)  # 每 300ms 檢查
        self._restore_timer.timeout.connect(self._check_restore)  # 檢查回呼

    def toggle(self):  # 開關切換
        """切換 PiP 模式開關"""
        if self.is_pip_mode:  # 當前浮窗
            self.exit_pip()  # 退出浮窗
        else:  # 當前一般
            self.enter_pip()  # 進入浮窗

    def enter_pip(self):  # 進入浮窗
        """進入 PiP 模式"""
        if self.is_pip_mode:  # 已經進入
            return  # 結束執行

        target_widget = self.win.video_container or self.win.video_widget  # 目標組件
        if not target_widget:  # 無組件時
            return  # 結束執行

        # 1. 處理全屏
        self._was_fullscreen = self.win.isFullScreen() or getattr(self.win, 'is_fullscreen', False)  # 記錄全屏
        if self._was_fullscreen:  # 原本全屏
            if hasattr(self.win, 'exit_fullscreen'):  # 有退出法
                self.win.exit_fullscreen()  # 退出全屏
            else:  # 無退出法
                self.win.showNormal()  # 恢復一般
                
        # 隱藏控制條
        for bar_name in ['bottom_bar']:  # 遍歷條名
            bar = getattr(self.win, bar_name, None)  # 取得組件
            if bar and hasattr(bar, 'hide'):  # 可隱藏時
                bar.hide()  # 隱藏組件

        self.is_pip_mode = True  # 設為浮窗

        # 2. 建立浮窗
        if not self.pip_window:  # 無浮窗時
            self.pip_window = PiPFloatingWindow(self)  # 建浮窗物件

        # 3. 裝過濾器
        self.pip_window.installEventFilter(self)  # 裝過濾器
        self._apply_filter_recursive(target_widget, True)  # 遞歸安裝

        # 4. 搬移播放器
        self.pip_window.layout.addWidget(target_widget)  # 移入浮窗
        target_widget.show()  # 顯示組件

        # 5. 顯示與最小化
        self.pip_window.show()  # 顯示浮窗
        self.win.hide()  # 隱藏主窗

        # 延遲聚焦
        self._entering = True  # 標記進入中
        QTimer.singleShot(50, self._force_pip_focus)  # 延遲聚焦

    def _force_pip_focus(self):  # 強制聚焦
        """強行奪回 Windows 系統級輸入焦點"""
        if not self.is_pip_mode:  # 已退出 PiP
            return  # 不要再最小化主窗
        if hasattr(self, 'pip_window') and self.pip_window.isVisible():  # 浮窗可見
            self.pip_window.show()  # 顯示浮窗
            self.pip_window.raise_()  # 置頂浮窗
            self.pip_window.activateWindow()  # 激活視窗
            self.pip_window.setFocus()  # 取得焦點
        
        # 6. 定位右下角
        screen = self.win.screen() if hasattr(self.win, 'screen') and self.win.screen() else QGuiApplication.primaryScreen()  # 取得螢幕
        if screen:  # 有螢幕時
            geo = screen.availableGeometry()  # 可用區域
            margin = 20  # 邊距設定
            def_w, def_h = self.pip_window.PIP_DEFAULT_SIZE  # 預設尺寸
            self.pip_window.resize(def_w, def_h)  # 調整大小
            x = geo.x() + geo.width() - def_w - margin  # 計算 X 軸
            y = geo.y() + geo.height() - def_h - margin  # 計算 Y 軸
            self.pip_window.move(x, y)  # 移動浮窗
        
        self.win.showMinimized()  # 主窗最小
        QTimer.singleShot(200, self._finish_entering)  # 等狀態穩定後解除標記
        self._restore_timer.start()  # 開始監測任務欄還原

    def _finish_entering(self):  # 進入完成
        self._entering = False  # 解除標記

    def _check_restore(self):  # 檢查主窗
        if not self.is_pip_mode:  # 已退出
            self._restore_timer.stop()  # 停止監測
            return  # 結束
        if self._entering:  # 進入中
            return  # 先不判斷
        if self.win.isVisible() and not self.win.isMinimized() and not self.win.isFullScreen():  # 已被還原
            self._restore_timer.stop()  # 停止監測
            self.exit_pip()  # 恢復主視窗

    def exit_pip(self):  # 退出浮窗
        """退出 PiP 模式"""
        if not self.is_pip_mode:  # 未開浮窗
            return  # 結束執行

        self.is_pip_mode = False  # 取消浮窗
        self._entering = False  # 清除進入標記
        self._restore_timer.stop()  # 停止監測

        target_widget = self.win.video_container or self.win.video_widget  # 目標組件

        # 1. 卸載過濾器
        if self.pip_window:  # 浮窗存在
            self.pip_window.removeEventFilter(self)  # 移除過濾
            self.pip_window.hide()  # 隱藏浮窗

        if target_widget:  # 組件存在
            self._apply_filter_recursive(target_widget, False)  # 遞歸移除

        # 2. 搬回主視窗
        if target_widget and hasattr(self.win, 'player_layout'):  # 佈局存在
            self.win.player_layout.insertWidget(1, target_widget, stretch=1)  # 移回主窗
            target_widget.show()  # 顯示組件

        # 3. 恢復主視窗
        if self._was_fullscreen:  # 原本全屏
            self.win.showNormal()  # 恢復一般
            if hasattr(self.win, 'enter_fullscreen'):  # 有全屏法
                self.win.enter_fullscreen()  # 進入全屏
            else:  # 無全屏法
                self.win.showFullScreen()  # 強制全屏
        else:  # 原本一般
            self.win.showNormal()  # 恢復一般
            
        # 4. 顯示控制條
        if hasattr(self.win, 'bottom_bar') and self.win.bottom_bar:  # 有底欄時
            self.win.bottom_bar.show()  # 顯示底欄

        self.win.activateWindow()  # 激活主窗

    def eventFilter(self, watched, event):  # 事件過濾
        """強行攔截所有雙擊與全屏觸發鍵"""
        if self.is_pip_mode:  # 浮窗模式
            # 1. 攔截雙擊
            if event.type() == QEvent.Type.MouseButtonDblClick:  # 雙擊事件
                return True  # 攔截吃掉
            # 2. 攔截按鍵
            if event.type() == QEvent.Type.KeyPress:  # 按鍵事件
                if event.key() in (Qt.Key.Key_F11, Qt.Key.Key_Escape, Qt.Key.Key_Return):  # 特定按鍵
                    return True  # 攔截吃掉
        return super().eventFilter(watched, event)  # 預設過濾

    def _apply_filter_recursive(self, widget, install=True):  # 遞歸過濾
        """遞歸安裝過濾器，確保子組件無一漏網"""
        if not widget:  # 組件空白
            return  # 結束執行
        if install:  # 需要安裝
            widget.installEventFilter(self)  # 安裝過濾
        else:  # 需要移除
            widget.removeEventFilter(self)  # 移除過濾
        for child in widget.findChildren(QWidget):  # 遍歷子件
            if install:  # 需要安裝
                child.installEventFilter(self)  # 安裝過濾
            else:  # 需要移除
                child.removeEventFilter(self)  # 移除過濾
# [代碼終點]