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

## Conda Setup

```powershell
conda create -n snipaste_nano python=3.11 -y
conda activate snipaste_nano
pip install -r requirements.txt
python main.py
```

## Usage

- Press `F1` to start a capture.
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
- This MVP uses the primary monitor and does not handle multi-monitor capture.
- Close the app with `Ctrl+C` in the terminal.

## Stack Notes

This prototype uses **PySide6** with native Qt screen capture and a Win32
global hotkey via `ctypes` (no external hotkey libraries).
