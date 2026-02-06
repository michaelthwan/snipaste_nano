# Snipaste Nano (Prototype)

Lightweight prototype of a Snipaste-like workflow using Python + Qt. Press
`F1` to draw a rectangle, then a floating window shows the capture. Drag the
floating window to move it, and press `Esc` to close it when focused.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Usage

- Press `F1` to start a capture.
- Click-and-drag to select the rectangle.
- Release to capture and show the floating image window.
- Drag the floating window to reposition it.
- Click the image to focus it, then press `Esc` to close it.

## Notes

- Global `F1` uses Win32 `RegisterHotKey` via `ctypes`. If policy blocks it,
  `F1` will not trigger; the rest of the app still runs.
- This MVP uses the primary monitor and does not handle multi-monitor capture.
- Close the app with `Ctrl+C` in the terminal.

## Stack Notes

This prototype uses **PySide6** with native Qt screen capture and a Win32
global hotkey via `ctypes` (no external hotkey libraries).
