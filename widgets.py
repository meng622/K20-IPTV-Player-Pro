# widgets.py
from config import *

# ==================== 現代極簡漸變進度條 ====================
class FlatGradientSlider(QSlider):
    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        # 有爸爸視窗
        if parent is not None:
            # 傳兩個盒子
            super().__init__(orientation, parent)
        # 無爸爸視窗
        else:
            # 只傳一個盒子
            super().__init__(orientation)

        # 固定高度
        self.setFixedHeight(12)
        # 滑鼠手勢
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 底條顏色
        self.color_track = QColor("#616161")
        # 滑塊顏色
        self.color_handle = QColor("#ffffff")
        # 漸變起點
        self.color_start = QColor("#6366f1")
        # 漸變中點
        self.color_mid = QColor("#a855f7")
        # 漸變終點
        self.color_end = QColor("#06b6d4")
        
    def mousePressEvent(self, event):
        # 判斷左鍵點擊
        if event.button() == Qt.MouseButton.LeftButton:
            # 水平軌道計算
            if self.orientation() == Qt.Orientation.Horizontal:
                # 計算點擊位置比例
                val = QStyle.sliderValueFromPosition(
                    self.minimum(),
                    self.maximum(),
                    int(event.position().x()),
                    self.width()
                )
            # 垂直軌道計算
            else:
                # 計算點擊位置比例
                val = QStyle.sliderValueFromPosition(
                    self.minimum(),
                    self.maximum(),
                    int(event.position().y()),
                    self.height(),
                    bInverse=True
                )
            # 設定最新數值
            self.setValue(val)
            # 發射滑動訊號
            self.sliderMoved.emit(val)
            # 標記事件已處理
            event.accept()

        # 呼叫父類點擊邏輯 (觸發 sliderPressed / sliderReleased)
        super().mousePressEvent(event)

    def set_theme_colors(self, start_hex, mid_hex, end_hex, track_hex="#616161", handle_hex="#ffffff"):
        # 更新顏色
        self.color_start = QColor(start_hex)
        # 更新顏色
        self.color_mid = QColor(mid_hex)
        # 更新顏色
        self.color_end = QColor(end_hex)
        # 更新顏色
        self.color_track = QColor(track_hex)
        # 更新顏色
        self.color_handle = QColor(handle_hex)
        # 強制重畫
        self.update()

    def paintEvent(self, event):
        # 建立畫筆
        painter = QPainter(self)
        # 開啟抗鋸齒
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 元件尺寸
        w, h = self.width(), self.height()
        # 軌道高度
        track_h = 4
        # 軌道位置
        track_y = (h - track_h) / 2

        # 畫底條
        painter.setPen(Qt.PenStyle.NoPen)
        # 填滿底條
        painter.setBrush(self.color_track)
        # 繪製底條
        painter.drawRoundedRect(QRectF(0, track_y, w, track_h), 2, 2)

        # 計算比例
        val_range = self.maximum() - self.minimum()
        # 進度百分比
        ratio = (self.value() - self.minimum()) / val_range if val_range > 0 else 0
        # 進度寬度
        fill_w = w * ratio

        # 畫進度條
        if fill_w > 0:
            # 建立漸變
            gradient = QLinearGradient(0, 0, fill_w, 0)
            # 起始色彩
            gradient.setColorAt(0.0, self.color_start)
            # 中間色彩
            gradient.setColorAt(0.5, self.color_mid)
            # 結束色彩
            gradient.setColorAt(1.0, self.color_end)

            # 填滿漸變
            painter.setBrush(gradient)
            # 繪製進度
            painter.drawRoundedRect(QRectF(0, track_y, fill_w, track_h), 2, 2)

        # 計算滑塊
        handle_radius = 5
        # 滑塊位置
        handle_x = max(handle_radius, min(w - handle_radius, fill_w))
        # 填滿滑塊
        painter.setBrush(self.color_handle)
        # 繪製滑塊
        painter.drawEllipse(QRectF(handle_x - handle_radius, (h / 2) - handle_radius, handle_radius * 2, handle_radius * 2))

# ==================== 自訂分割條 ====================        
class CustomSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        """🎯 原生繪畫事件：動態抓取 main_window 當前主題色彩 (隨皮膚切換連動)"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 🎯 從主視窗動態獲取當前主題配色 (魅紫/霓藍/翡翠/鈦空灰)
        main_win = self.window()
        c = getattr(main_win, 'current_theme_config', {})
        
        # 抓取主題的邊框色與高亮強調色 (抓不到時預設備用色)
        theme_border = c.get('border', '#8b5cf6')
        theme_accent = c.get('accent', '#00f2fe')

        # 🎯 依據滑鼠懸停/常態動態取色
        if self.underMouse():
            bg_color = QColor(theme_accent)  # 滑鼠懸停：當前主題高亮色 (Accent)
            dot_color = QColor("#ffffff")    # 抓手點點：亮白
        else:
            bg_color = QColor(theme_border)  # 平時常態：當前主題邊框色 (Border)
            dot_color = QColor("#ffffff")    # 抓手點點：亮白

        # 1. 繪製手柄背景
        painter.fillRect(self.rect(), bg_color)

        # 2. 繪製中間 6 個高亮抓手點點
        rect = self.rect()
        cx, cy = rect.center().x(), rect.center().y()
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)

        # 垂直/水平方向繪製 6 個小圓點
        if self.orientation() == Qt.Orientation.Horizontal:
            for offset in [-15, -9, -3, 3, 9, 15]:
                painter.drawEllipse(int(cx - 1), int(cy + offset - 1), 3, 3)
        else:
            for offset in [-15, -9, -3, 3, 9, 15]:
                painter.drawEllipse(int(cx + offset - 1), int(cy - 1), 3, 3)

# ==================== 自訂分割容器 ====================  
class CustomSplitter(QSplitter):
    def createHandle(self):  # 建立控制手柄
        return CustomSplitterHandle(self.orientation(), self)  # 返回自訂手柄

# ==================== 自訂圓角選單 ====================  
class RoundedMenu(QMenu):
    def __init__(self, parent=None):  # 初始化選單
        super().__init__(parent)  # 呼叫父類初始化
        # 關鍵：啟用背景透明，解決圓角黑邊/方角問題
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 設定背景透明
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)  # 隱藏原生邊框
        
        