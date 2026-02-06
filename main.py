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

    def __init__(self, screen: QtGui.QScreen) -> None:
        super().__init__()
        self._screen = screen
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
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 90))
        rect = self._selection_rect()
        if rect is not None and rect.width() > 0 and rect.height() > 0:
            pen = QtGui.QPen(QtGui.QColor(255, 80, 80), 2)
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
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QtWidgets.QLabel(self)
        self._label.setPixmap(pixmap)
        self._label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._label)

        self.resize(pixmap.size())

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.activateWindow()
        self.raise_()
        self._drag_offset = event.position().toPoint()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_offset is None:
            return
        global_pos = event.globalPosition().toPoint()
        self.move(global_pos - self._drag_offset)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_offset = None

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()


class SnipasteNanoApp:
    def __init__(self) -> None:
        self.app = QtWidgets.QApplication(sys.argv)
        self.app.setApplicationName("Snipaste Nano")
        self._hotkey_registered = False
        self._overlay = None
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
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            print("No screen available for capture.")
            return
        self._overlay = CaptureOverlay(screen)
        self._overlay.captured.connect(self._handle_capture)
        self._overlay.cancelled.connect(self._clear_overlay)
        self._overlay.show()
        self._overlay.activateWindow()

    def _clear_overlay(self) -> None:
        if self._overlay is not None:
            self._overlay.deleteLater()
            self._overlay = None

    def _handle_capture(self, rect: QtCore.QRect) -> None:
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            self._clear_overlay()
            return
        self._clear_overlay()

        pixmap = screen.grabWindow(0)
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
