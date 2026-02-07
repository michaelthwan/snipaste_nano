import ctypes
import sys
from ctypes import wintypes

from PySide6 import QtCore, QtGui, QtWidgets

WM_HOTKEY = 0x0312
HOTKEY_ID = 1
MOD_NOREPEAT = 0x4000
VK_F1 = 0x70


class HotkeyFilter(QtCore.QAbstractNativeEventFilter):
    def __init__(self, callback) -> None:
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        if event_type in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self._callback()
                return True, 0
        return False, 0


class CaptureOverlay(QtWidgets.QWidget):
    captured = QtCore.Signal(QtCore.QRect)
    cancelled = QtCore.Signal()

    def __init__(self, screen: QtGui.QScreen, pixmap: QtGui.QPixmap) -> None:
        super().__init__()
        self._screen = screen
        self._pixmap = pixmap
        self._origin = None
        self._current = None
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setCursor(QtCore.Qt.CrossCursor)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self._set_geometry()

    def _set_geometry(self) -> None:
        geometry = self._screen.geometry()
        self.setGeometry(geometry)

    def _selection_rect(self) -> QtCore.QRect | None:
        if self._origin is None or self._current is None:
            return None
        rect = QtCore.QRect(self._origin, self._current).normalized()
        return rect

    def paintEvent(self, _event) -> None:
        painter = QtGui.QPainter(self)
        if not self._pixmap.isNull():
            painter.drawPixmap(self.rect(), self._pixmap)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 90))
        rect = self._selection_rect()
        if rect is not None and rect.width() > 0 and rect.height() > 0:
            if not self._pixmap.isNull():
                painter.drawPixmap(rect, self._pixmap, rect)
            pen = QtGui.QPen(QtGui.QColor(0, 0, 0), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton:
            return
        self._origin = event.position().toPoint()
        self._current = self._origin
        self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._origin is None:
            return
        self._current = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton:
            return
        rect = self._selection_rect()
        if rect is None or rect.width() < 4 or rect.height() < 4:
            self.cancelled.emit()
            self.close()
            return
        self.captured.emit(rect)
        self.close()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key_Escape:
            self.cancelled.emit()
            self.close()


class FloatingWindow(QtWidgets.QWidget):
    def __init__(self, pixmap: QtGui.QPixmap) -> None:
        super().__init__()
        self._drag_offset = None
        self._base_pixmap = pixmap
        self._image = pixmap.toImage().convertToFormat(QtGui.QImage.Format_ARGB32)
        self._scale = 1.0
        self._pen_active = False
        self._brush_size = 6
        self._brush_color = QtGui.QColor(220, 30, 30)
        self._drawing = False
        self._last_point = None
        self._color_popup = None
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toolbar = QtWidgets.QWidget(self)
        self._toolbar.setVisible(False)
        self._toolbar_layout = QtWidgets.QHBoxLayout(self._toolbar)
        self._toolbar_layout.setContentsMargins(6, 4, 6, 4)
        self._toolbar_layout.setSpacing(6)

        self._size_button = SizeButton(self._brush_size, self._brush_color, self)
        self._size_button.sizeChanged.connect(self._on_brush_size_changed)
        self._toolbar_layout.addWidget(self._size_button)

        self._pen_button = QtWidgets.QToolButton(self._toolbar)
        self._pen_button.setText("✎")
        self._pen_button.setCheckable(True)
        self._pen_button.clicked.connect(self._toggle_pen)
        self._pen_button.setFixedSize(32, 32)
        self._update_pen_button_style()
        self._toolbar_layout.addWidget(self._pen_button)

        self._copy_button = QtWidgets.QToolButton(self._toolbar)
        self._copy_button.setText("Copy")
        self._copy_button.clicked.connect(self.copy_to_clipboard)
        self._toolbar_layout.addWidget(self._copy_button)

        self._toolbar_layout.addStretch(1)

        self._canvas = CanvasWidget(self._image, self)
        layout.addWidget(self._canvas)
        layout.addWidget(self._toolbar)

        self._escape_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Escape), self
        )
        self._escape_shortcut.activated.connect(self._handle_escape)
        self._space_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Space), self
        )
        self._space_shortcut.activated.connect(self._toggle_toolbar)
        self._copy_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence.Copy, self
        )
        self._copy_shortcut.activated.connect(self.copy_to_clipboard)

        self._apply_scale()
        self.adjustSize()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton:
            return
        if self._pen_active:
            return
        self._begin_drag(event.globalPosition().toPoint(), event.position().toPoint())

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_offset is None:
            return
        self._perform_drag(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_offset = None

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key_Escape:
            self._handle_escape()
        elif event.key() == QtCore.Qt.Key_Space:
            self._toggle_toolbar()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if self._pen_active:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.1 if delta > 0 else 0.9
        self._scale = max(0.2, min(5.0, self._scale * factor))
        self._apply_scale()

    def _apply_scale(self) -> None:
        size = self._base_pixmap.size()
        new_size = QtCore.QSize(
            int(size.width() * self._scale), int(size.height() * self._scale)
        )
        if new_size.width() < 1 or new_size.height() < 1:
            return
        self._canvas.set_scale(self._scale)
        self._canvas.setFixedSize(new_size)
        self.adjustSize()

    def _begin_drag(self, global_pos: QtCore.QPoint, local_pos: QtCore.QPoint) -> None:
        self.activateWindow()
        self.raise_()
        self._drag_offset = local_pos
        self._perform_drag(global_pos)

    def _perform_drag(self, global_pos: QtCore.QPoint) -> None:
        if self._drag_offset is None:
            return
        self.move(global_pos - self._drag_offset)

    def _toggle_pen(self) -> None:
        self._set_pen_active(self._pen_button.isChecked())
        if self._pen_active:
            self._show_color_popup()
        else:
            self._close_color_popup()

    def _set_pen_active(self, active: bool) -> None:
        self._pen_active = active
        self._pen_button.setChecked(active)
        self._canvas.set_pen_active(active)
        if not active:
            self.end_draw()
        self._canvas.setCursor(
            QtCore.Qt.CrossCursor if active else QtCore.Qt.ArrowCursor
        )

    def _toggle_toolbar(self) -> None:
        self._toolbar.setVisible(not self._toolbar.isVisible())
        if not self._toolbar.isVisible():
            self._set_pen_active(False)
            self._close_color_popup()
        self.adjustSize()

    def _handle_escape(self) -> None:
        if self._pen_active or self._toolbar.isVisible():
            self._set_pen_active(False)
            self._toolbar.setVisible(False)
            self._close_color_popup()
            self.adjustSize()
            return
        self.close()

    def _show_color_popup(self) -> None:
        if self._color_popup is not None:
            self._color_popup.close()
        self._color_popup = ColorPopup(self._brush_color, self)
        self._color_popup.colorSelected.connect(self._set_brush_color)
        button_pos = self._pen_button.mapToGlobal(QtCore.QPoint(0, 0))
        self._color_popup.adjustSize()
        popup_height = self._color_popup.sizeHint().height()
        self._color_popup.move(
            button_pos.x(),
            button_pos.y() - popup_height - 4,
        )
        self._color_popup.show()

    def _close_color_popup(self) -> None:
        if self._color_popup is not None:
            self._color_popup.close()
            self._color_popup = None

    def _set_brush_color(self, color: QtGui.QColor) -> None:
        self._brush_color = color
        self._update_pen_button_style()
        self._size_button.set_color(color)

    def _on_brush_size_changed(self, size: int) -> None:
        self._brush_size = size

    def _update_pen_button_style(self) -> None:
        self._pen_button.setStyleSheet(
            "QToolButton { background-color: %s; border: 1px solid #333; }"
            % self._brush_color.name()
        )

    def start_draw(self, pos: QtCore.QPoint) -> None:
        if not self._pen_active:
            return
        self._drawing = True
        self._last_point = pos

    def draw_to(self, pos: QtCore.QPoint) -> None:
        if not self._drawing or self._last_point is None:
            return
        painter = QtGui.QPainter(self._image)
        pen = QtGui.QPen(
            self._brush_color, self._brush_size, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap
        )
        painter.setPen(pen)
        painter.drawLine(self._last_point, pos)
        painter.end()
        self._last_point = pos
        self._canvas.update()

    def end_draw(self) -> None:
        self._drawing = False
        self._last_point = None

    def copy_to_clipboard(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setImage(self._image)


class CanvasWidget(QtWidgets.QWidget):
    def __init__(self, image: QtGui.QImage, parent: FloatingWindow) -> None:
        super().__init__(parent)
        self._image = image
        self._scale = 1.0
        self._pen_active = False

    def set_scale(self, scale: float) -> None:
        self._scale = scale
        self.update()

    def set_pen_active(self, active: bool) -> None:
        self._pen_active = active

    def paintEvent(self, _event) -> None:
        painter = QtGui.QPainter(self)
        target = QtCore.QRect(0, 0, self.width(), self.height())
        painter.drawImage(target, self._image)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton:
            return
        if self._pen_active:
            self.parent().start_draw(self._map_to_image(event.position().toPoint()))
        else:
            self.parent()._begin_drag(
                event.globalPosition().toPoint(), event.position().toPoint()
            )

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._pen_active:
            self.parent().draw_to(self._map_to_image(event.position().toPoint()))
        else:
            self.parent()._perform_drag(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton:
            return
        if self._pen_active:
            self.parent().end_draw()
        else:
            self.parent()._drag_offset = None

    def _map_to_image(self, point: QtCore.QPoint) -> QtCore.QPoint:
        if self._scale <= 0:
            return point
        x = int(point.x() / self._scale)
        y = int(point.y() / self._scale)
        x = max(0, min(self._image.width() - 1, x))
        y = max(0, min(self._image.height() - 1, y))
        return QtCore.QPoint(x, y)


class SizeButton(QtWidgets.QToolButton):
    sizeChanged = QtCore.Signal(int)

    def __init__(self, size: int, color: QtGui.QColor, parent=None) -> None:
        super().__init__(parent)
        self._size = size
        self._color = color
        self.setFixedSize(32, 32)
        self._update_icon()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        step = 1 if delta > 0 else -1
        self._size = max(1, min(40, self._size + step))
        self._update_icon()
        self.sizeChanged.emit(self._size)

    def set_color(self, color: QtGui.QColor) -> None:
        self._color = color
        self._update_icon()

    def _update_icon(self) -> None:
        pixmap = QtGui.QPixmap(24, 24)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        radius = max(2, min(10, self._size // 2))
        center = QtCore.QPoint(12, 12)
        painter.setBrush(self._color)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(center, radius, radius)
        painter.end()
        self.setIcon(QtGui.QIcon(pixmap))
        self.setIconSize(pixmap.size())
        self.setToolTip(f"Brush size: {self._size}")


class ColorPopup(QtWidgets.QFrame):
    colorSelected = QtCore.Signal(QtGui.QColor)

    def __init__(self, current: QtGui.QColor, parent=None) -> None:
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self._colors = [
            QtGui.QColor(0, 0, 0),
            QtGui.QColor(255, 255, 255),
            QtGui.QColor(220, 30, 30),
            QtGui.QColor(30, 120, 255),
            QtGui.QColor(30, 180, 90),
            QtGui.QColor(255, 200, 0),
            QtGui.QColor(160, 80, 200),
            QtGui.QColor(255, 120, 40),
            QtGui.QColor(120, 120, 120),
            QtGui.QColor(40, 40, 40),
        ]
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        for i, color in enumerate(self._colors):
            button = QtWidgets.QToolButton(self)
            button.setFixedSize(20, 20)
            button.setStyleSheet(
                "QToolButton { background-color: %s; border: 1px solid #222; }"
                % color.name()
            )
            if color == current:
                button.setStyleSheet(
                    "QToolButton { background-color: %s; border: 2px solid #fff; }"
                    % color.name()
                )
            button.clicked.connect(lambda _=False, c=color: self._select(c))
            layout.addWidget(button, i // 5, i % 5)

    def _select(self, color: QtGui.QColor) -> None:
        self.colorSelected.emit(color)
        self.close()


class SnipasteNanoApp:
    def __init__(self) -> None:
        self.app = QtWidgets.QApplication(sys.argv)
        self.app.setApplicationName("Snipaste Nano")
        self._hotkey_registered = False
        self._overlay = None
        self._capture_pixmap = None
        self._capture_screen = None
        self._floating_windows = []

        self._hotkey_filter = HotkeyFilter(self.start_capture)
        self.app.installNativeEventFilter(self._hotkey_filter)
        self._register_hotkey()
        self.app.aboutToQuit.connect(self._cleanup_hotkey)

    def _register_hotkey(self) -> None:
        user32 = ctypes.windll.user32
        self._hotkey_registered = bool(
            user32.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT, VK_F1)
        )
        if not self._hotkey_registered:
            print("Warning: global F1 hotkey registration failed.")

    def _cleanup_hotkey(self) -> None:
        if self._hotkey_registered:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)

    def start_capture(self) -> None:
        if self._overlay is not None:
            return
        cursor_pos = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(cursor_pos)
        if screen is None:
            screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            print("No screen available for capture.")
            return
        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            print("No screen content available for capture.")
            return
        self._capture_pixmap = pixmap
        self._capture_screen = screen
        self._overlay = CaptureOverlay(screen, pixmap)
        self._overlay.captured.connect(self._handle_capture)
        self._overlay.cancelled.connect(self._clear_overlay)
        self._overlay.show()
        self._overlay.activateWindow()

    def _clear_overlay(self) -> None:
        if self._overlay is not None:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        self._capture_pixmap = None
        self._capture_screen = None

    def _handle_capture(self, rect: QtCore.QRect) -> None:
        pixmap = self._capture_pixmap
        screen = self._capture_screen
        self._clear_overlay()

        if pixmap is None or pixmap.isNull():
            if screen is None:
                screen = QtGui.QGuiApplication.primaryScreen()
            if screen is None:
                return
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                return
        ratio = pixmap.devicePixelRatio()
        scaled_rect = QtCore.QRect(
            int(rect.x() * ratio),
            int(rect.y() * ratio),
            int(rect.width() * ratio),
            int(rect.height() * ratio),
        )
        scaled_rect = scaled_rect.intersected(
            QtCore.QRect(0, 0, pixmap.width(), pixmap.height())
        )
        if scaled_rect.width() < 1 or scaled_rect.height() < 1:
            return
        cropped = pixmap.copy(scaled_rect)
        cropped.setDevicePixelRatio(ratio)
        self._show_floating(cropped)

    def _show_floating(self, pixmap: QtGui.QPixmap) -> None:
        floating = FloatingWindow(pixmap)
        self._floating_windows.append(floating)
        floating.destroyed.connect(
            lambda _obj=None, win=floating: self._discard_window(win)
        )
        floating.show()
        floating.activateWindow()

    def _discard_window(self, window: FloatingWindow) -> None:
        try:
            self._floating_windows.remove(window)
        except ValueError:
            pass

    def run(self) -> int:
        return self.app.exec()


if __name__ == "__main__":
    app = SnipasteNanoApp()
    sys.exit(app.run())
