# gui/scalable_label.py

from PyQt5.QtWidgets import QLabel, QSizePolicy, QScrollArea
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QSize, QPoint

class ScalableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        
        self._panning = False
        self._last_pos = QPoint()
        self.setCursor(Qt.OpenHandCursor) # 默认显示手型光标
        
        self._pixmap = QPixmap()
        self.scale_factor = 1.0
        self.base_pixmap = QPixmap() # 存储未缩放的原始图像
        self.original_width = self.width()
        self.original_height = self.height()
        

    def set_image(self, pixmap: QPixmap):
        """设置新的图像，并重置缩放因子"""
        if pixmap.isNull():
            self.setText("Failed to load image.")
            self.base_pixmap = QPixmap()
            self._pixmap = QPixmap()
            self.scale_factor = 1.0
        else:
            self.base_pixmap = pixmap
            self.scale_factor = 1.0
            self.update_pixmap()

    def clear_image(self):
        # 清空 pixmap 本体
        self._pixmap = QPixmap()
        super().setPixmap(self._pixmap)
        self.base_pixmap = QPixmap()
        self.setFixedSize(512, 512)
        self.scale_factor = 1.0
        # 通知 scrollArea 的内部 widget 尺寸更新
        pw = self.parentWidget()
        if pw:
            pw.adjustSize()

    def update_pixmap(self):
        """根据当前缩放因子和原始图像更新显示"""
        if self.base_pixmap.isNull():
            return

        # 计算新的大小
        new_size = self.base_pixmap.size() * self.scale_factor
        new_width = int(new_size.width())
        new_height = int(new_size.height())
        # 使用平滑缩放
        self._pixmap = self.base_pixmap.scaled(
            new_width,
            new_height,
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        super().setPixmap(self._pixmap)
        
        # 调整 QLabel 的大小以适应缩放后的图像
        self.setFixedSize(self._pixmap.size())
        self.parentWidget().adjustSize() # 确保父布局更新 (如果它依赖子控件的大小)


    def wheelEvent(self, event):
        """处理鼠标滚轮事件进行缩放"""
        scroll_degrees = event.angleDelta().y() / 8 / 15 # 获取滚轮度数
        
        if scroll_degrees > 0:
            # 放大 (最小放大比例为 1.25)
            self.scale_factor *= 1.25
        elif scroll_degrees < 0:
            # 缩小 (最大缩小比例为 0.8)
            self.scale_factor *= 0.8
        
        # 限制缩放范围 (例如 0.1 到 10.0)
        self.scale_factor = max(0.1, min(10.0, self.scale_factor))
        
        self.update_pixmap()
        
    def resizeEvent(self, event):
        """处理窗口大小变化时，如果未设置固定大小，则重新绘制"""
        # 如果设置了固定大小，则不需要重绘，否则如果被放置在布局中，可能需要。
        # 由于我们在 update_pixmap 中设置了 setFixedSize，这里通常不做处理。
        super().resizeEvent(event)
        
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._panning = True
            self._last_pos = event.globalPos()
            self.setCursor(Qt.ClosedHandCursor)   # 按下时变成握拳
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            # 当前鼠标位置
            delta = event.globalPos() - self._last_pos
            self._last_pos = event.globalPos()

            # 关键：移动 QLabel 的位置
            self.move(self.x() + delta.x(), self.y() + delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._panning = False
            self.setCursor(Qt.OpenHandCursor)  # 松开恢复张开手型
        super().mouseReleaseEvent(event)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._panning = True
            self._last_pos = event.globalPos()
            self.setCursor(Qt.ClosedHandCursor)   # 按下时变成握拳
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            # 当前鼠标位置
            delta = event.globalPos() - self._last_pos
            self._last_pos = event.globalPos()

            # 关键：移动 QLabel 的位置
            self.move(self.x() + delta.x(), self.y() + delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._panning = False
            self.setCursor(Qt.OpenHandCursor)  # 松开恢复张开手型
        super().mouseReleaseEvent(event)
