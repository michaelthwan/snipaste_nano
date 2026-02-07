# Snipaste Nano (Prototype)

Lightweight prototype of a Snipaste-like workflow using Python + Qt. Press
`F1` (Windows) or `fn+F1` (macOS) to draw a rectangle, then a floating window
shows the capture. Drag the floating window to move it, and press `Esc` to
close it when focused.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Conda Setup

```powershell
conda create -n snipaste_nano python=3.11 -y
conda activate snipaste_nano
pip install -r requirements.txt
python main.py
```

## UV Setup

```cmd
uv venv
.\.venv\Scripts\activate
uv pip install -r requirements.txt
python main.py
```

## Usage

- Press `F1` (Windows) or `fn+F1` (macOS) to start a capture.
- Click-and-drag to select the rectangle.
- Release to capture and show the floating image window.
- Drag the floating window to reposition it.
- Press `Space` while focused to toggle the toolbar.
- Click the pen tool to pick a color, then draw on the image.
- Scroll the size button to change brush size.
- Press `Ctrl+C` (normal mode) or click `Copy` to copy to clipboard.
- Press `Esc` once to exit pen mode and hide toolbar; press again to close.

## Notes

- Global `F1` uses Win32 `RegisterHotKey` via `ctypes`. If policy blocks it,
  `F1` will not trigger; the rest of the app still runs.
- On macOS, install `pyobjc-framework-Cocoa==12.1` and use `fn+F1` (or enable
  "Use F1, F2, etc. keys as standard function keys" to use `F1` alone).
- macOS may prompt for Input Monitoring permission so the global hotkey works.
- Capture activates on the monitor under the mouse cursor.
- Close the app with `Ctrl+C` in the terminal.

## Stack Notes

This prototype uses **PySide6** with native Qt screen capture and a Win32
global hotkey via `ctypes` (no external hotkey libraries).
