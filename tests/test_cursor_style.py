import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets

from main import (
    PALETTE_COLUMNS,
    PALETTE_COLORS,
    TOOL_ICON_SIZE,
    FloatingWindow,
    build_selection_cursor_pixmap,
    build_tool_icon,
    clamp_brush_size,
    clamp_text_size,
    draw_text_on_image,
    SizeButton,
)


class CursorStyleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_brush_size_is_clamped_to_supported_range(self) -> None:
        self.assertEqual(clamp_brush_size(-5), 1)
        self.assertEqual(clamp_brush_size(6), 6)
        self.assertEqual(clamp_brush_size(99), 40)

    def test_text_size_is_clamped_to_supported_range(self) -> None:
        self.assertEqual(clamp_text_size(-5), 8)
        self.assertEqual(clamp_text_size(18), 18)
        self.assertEqual(clamp_text_size(200), 96)

    def test_selection_cursor_uses_color_for_crosshair_and_center_dot(self) -> None:
        color = QtGui.QColor(17, 130, 240)
        pixmap = build_selection_cursor_pixmap(color, 8)
        image = pixmap.toImage()
        center = image.width() // 2

        self.assertEqual(image.pixelColor(center, center), color)
        self.assertEqual(image.pixelColor(center, 2), color)
        self.assertEqual(image.pixelColor(2, center), color)
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)

    def test_wheel_delta_adjusts_brush_size_without_size_button_hover(self) -> None:
        window = FloatingWindow(QtGui.QPixmap(20, 20))
        window._brush_size = 6

        window.adjust_brush_size_from_wheel_delta(120)
        self.assertEqual(window._brush_size, 7)

        window.adjust_brush_size_from_wheel_delta(-120)
        self.assertEqual(window._brush_size, 6)

    def test_toolbar_does_not_show_size_tile_as_a_tool_button(self) -> None:
        window = FloatingWindow(QtGui.QPixmap(20, 20))

        self.assertEqual(window._toolbar.findChildren(SizeButton), [])

    def test_toolbar_contains_line_pen_text_and_copy_buttons(self) -> None:
        window = FloatingWindow(QtGui.QPixmap(20, 20))
        tooltips = []
        for i in range(window._toolbar_layout.count()):
            widget = window._toolbar_layout.itemAt(i).widget()
            if isinstance(widget, QtWidgets.QToolButton):
                tooltips.append(widget.toolTip())

        self.assertEqual(tooltips, ["Line", "Pen", "Text", "Copy"])

    def test_palette_matches_compact_reference_grid(self) -> None:
        self.assertEqual(len(PALETTE_COLORS), 20)
        self.assertEqual(PALETTE_COLUMNS, 10)
        self.assertEqual(PALETTE_COLORS[0].name(), "#000000")
        self.assertIn("#ff3030", [color.name() for color in PALETTE_COLORS[:10]])
        self.assertEqual(PALETTE_COLORS[10].name(), "#ffffff")

    def test_tool_icons_have_readable_compact_glyphs(self) -> None:
        self.assertEqual(TOOL_ICON_SIZE, 22)
        for name in ("pen", "line", "text", "copy"):
            icon = build_tool_icon(name, QtGui.QColor("#222222"))
            image = icon.toImage()

            self.assertEqual(icon.size().width(), TOOL_ICON_SIZE)
            self.assertEqual(icon.size().height(), TOOL_ICON_SIZE)
            xs = []
            ys = []
            for y in range(image.height()):
                for x in range(image.width()):
                    if image.pixelColor(x, y).alpha() > 0:
                        xs.append(x)
                        ys.append(y)

            self.assertGreater(len(xs), 18, name)
            self.assertGreaterEqual(max(xs) - min(xs), 6, name)
            self.assertGreaterEqual(max(ys) - min(ys), 6, name)
            self.assertGreaterEqual(min(xs), 2, name)
            self.assertLessEqual(max(xs), TOOL_ICON_SIZE - 3, name)
            self.assertGreaterEqual(min(ys), 2, name)
            self.assertLessEqual(max(ys), TOOL_ICON_SIZE - 3, name)

    def test_draw_text_on_image_renders_text_color(self) -> None:
        image = QtGui.QImage(120, 60, QtGui.QImage.Format_ARGB32)
        image.fill(QtGui.QColor("#ffffff"))
        color = QtGui.QColor("#ff3030")

        draw_text_on_image(image, "Hi", QtCore.QPoint(8, 8), color, 20)

        changed_pixels = 0
        for y in range(image.height()):
            for x in range(image.width()):
                pixel = image.pixelColor(x, y)
                if pixel.red() > 200 and pixel.green() < 120 and pixel.blue() < 120:
                    changed_pixels += 1
        self.assertGreater(changed_pixels, 0)


if __name__ == "__main__":
    unittest.main()
