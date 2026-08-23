"""
pip_manager.py - 獨立畫中畫 (PiP) 模式管理器
"""
from PyQt6.QtCore import QObject, Qt, QEvent, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizeGrip, QPushButton



class PiPFloatingWindow(QWidget):
    """獨立 PiP 置頂浮窗容器"""

    def __init__(self, pip_mgr):
        super().__init__()
        self.pip_mgr = pip_mgr
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        # 16:9 尺寸限制 ( 240p / 360p / 480p )
        self.PIP_MIN_SIZE = (426, 240)      # 240p
        self.PIP_DEFAULT_SIZE = (640, 360)  # 360p
        self.PIP_MAX_SIZE = (854, 480)      # 480p

        self.setMinimumSize(*self.PIP_MIN_SIZE)
        self.setMaximumSize(*self.PIP_MAX_SIZE)
        self.resize(*self.PIP_DEFAULT_SIZE)

        # 佈局設定
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 右上角關閉按鈕
        self.btn_restore = QPushButton("✕", self)
        self.btn_restore.setFixedSize(26, 26)
        self.btn_restore.setToolTip("退出畫中畫並恢復主視窗")
        self.btn_restore.setStyleSheet(
            "QPushButton { background: rgba(0,0,0,0.65); color: #ffffff; border: none; font-weight: bold; border-bottom-left-radius: 6px; }"
            "QPushButton:hover { background: #ff4d4f; }"
        )
        self.btn_restore.clicked.connect(self.pip_mgr.exit_pip)

        # 右下角縮放把手
        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setFixedSize(16, 16)

        self._drag_pos = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        
        # 防止 resize 遞歸觸發
        if getattr(self, '_resizing', False):
            return
        self._resizing = True

        # 強制鎖定 16:9 比例 (以寬度為基準計算高度)
        target_w = self.width()
        target_h = int(target_w * 9 / 16)

        # 結合最大/最小尺寸邊界限制
        min_w, min_h = getattr(self, 'PIP_MIN_SIZE', (426, 240))
        max_w, max_h = getattr(self, 'PIP_MAX_SIZE', (854, 480))
        clamped_w = max(min_w, min(target_w, max_w))
        clamped_h = max(min_h, min(target_h, max_h))

        if self.width() != clamped_w or self.height() != clamped_h:
            self.resize(clamped_w, clamped_h)

        # 動態保持按鈕與 SizeGrip 貼合角落
        self.btn_restore.move(self.width() - 26, 0)
        self.btn_restore.raise_()
        self.sizegrip.move(self.width() - 16, self.height() - 16)
        self.sizegrip.raise_()

        self._resizing = False
        
        self.btn_restore.move(self.width() - 26, 0)
        self.btn_restore.raise_()
        self.sizegrip.move(self.width() - 16, self.height() - 16)
        self.sizegrip.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        self.btn_restore.raise_()
        self.sizegrip.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.btn_restore.geometry().contains(event.pos()) and not self.sizegrip.geometry().contains(event.pos()):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        """徹底屏蔽浮窗本體的雙擊"""
        event.accept()


class PiPManager(QObject):
    """獨立畫中畫 (PiP) 管理器"""

    def __init__(self, main_win):
        super().__init__(main_win)
        self.win = main_win
        self.is_pip_mode = False
        self.pip_window = None
        self._was_fullscreen = False

    def toggle(self):
        """切換 PiP 模式開關"""
        if self.is_pip_mode:
            self.exit_pip()
        else:
            self.enter_pip()

    def enter_pip(self):
        """進入 PiP 模式"""
        if self.is_pip_mode:
            return

        target_widget = getattr(self.win, 'video_container', None) or getattr(self.win, 'video_widget', None)
        if not target_widget:
            return

        # 1. 記錄全屏狀態並安全退出全屏
        self._was_fullscreen = self.win.isFullScreen() or getattr(self.win, 'is_fullscreen', False)
        if self._was_fullscreen:
            if hasattr(self.win, 'exit_fullscreen'):
                self.win.exit_fullscreen()
            else:
                self.win.showNormal()
                
        # 強行隱藏主視窗所有可能殘留的全屏控制條
        for bar_name in ['bottom_bar']:
            bar = getattr(self.win, bar_name, None)
            if bar and hasattr(bar, 'hide'):
                bar.hide()  

        self.is_pip_mode = True

        # 2. 建立獨立浮窗
        if not self.pip_window:
            self.pip_window = PiPFloatingWindow(self)

        # 3. 安裝過濾器（同時鎖死浮窗與影片組件）
        self.pip_window.installEventFilter(self)
        self._apply_filter_recursive(target_widget, True)

        # 4. 搬移播放組件至獨立浮窗
        self.pip_window.layout.addWidget(target_widget)
        target_widget.show()

        # 5. 顯示浮窗，主視窗最小化
        self.pip_window.show()
        if hasattr(self.win, 'hide'):
                self.win.hide()  # 或 showMinimized()

        # 🎯 用 QTimer 延遲 50ms，避開 Windows 隱藏視窗時的焦點轉移
        QTimer.singleShot(50, self._force_pip_focus)

    def _force_pip_focus(self):
        """強行奪回 Windows 系統級輸入焦點"""
        if hasattr(self, 'pip_window') and self.pip_window.isVisible():
            self.pip_window.show()
            self.pip_window.raise_()
            self.pip_window.activateWindow()
            self.pip_window.setFocus()
        
        # 6. 自動定位至螢幕右下角（自動避開 Taskbar 工作列）
        screen = self.win.screen() if hasattr(self.win, 'screen') and self.win.screen() else QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            margin = 20
            def_w, def_h = self.pip_window.PIP_DEFAULT_SIZE
            self.pip_window.resize(def_w, def_h)
            x = geo.x() + geo.width() - def_w - margin
            y = geo.y() + geo.height() - def_h - margin
            self.pip_window.move(x, y)
        
        self.win.showMinimized()

    def exit_pip(self):
        """退出 PiP 模式"""
        if not self.is_pip_mode:
            return

        self.is_pip_mode = False

        target_widget = getattr(self.win, 'video_container', None) or getattr(self.win, 'video_widget', None)

        # 1. 卸載過濾器與隱藏浮窗
        if self.pip_window:
            self.pip_window.removeEventFilter(self)
            self.pip_window.hide()

        if target_widget:
            self._apply_filter_recursive(target_widget, False)

        # 2. 將播放組件搬回主視窗 Layout
        if target_widget and hasattr(self.win, 'player_layout'):
            self.win.player_layout.insertWidget(1, target_widget, stretch=1)
            target_widget.show()

        # 3. 恢復主視窗狀態（若原本是全屏則恢復全屏，否則正常顯示）
        if self._was_fullscreen:
            self.win.showNormal()
            if hasattr(self.win, 'enter_fullscreen'):
                self.win.enter_fullscreen()
            else:
                self.win.showFullScreen()
        else:
            self.win.showNormal()
            
        # 4. 恢復主視窗控制條顯示
        if hasattr(self.win, 'bottom_bar') and self.win.bottom_bar:
            self.win.bottom_bar.show()

        self.win.activateWindow()

    def eventFilter(self, watched, event):
        """強行攔截所有雙擊與全屏觸發鍵"""
        if self.is_pip_mode:
            # 1. 攔截任何形式的鼠標雙擊
            if event.type() == QEvent.Type.MouseButtonDblClick:
                return True
            # 2. 攔截按鍵（F11 / Esc / Enter）防止誤觸全屏
            if event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_F11, Qt.Key.Key_Escape, Qt.Key.Key_Return):
                    return True
        return super().eventFilter(watched, event)

    def _apply_filter_recursive(self, widget, install=True):
        """遞歸安裝過濾器，確保子組件無一漏網"""
        if not widget:
            return
        if install:
            widget.installEventFilter(self)
        else:
            widget.removeEventFilter(self)
        for child in widget.findChildren(QWidget):
            if install:
                child.installEventFilter(self)
            else:
                child.removeEventFilter(self)