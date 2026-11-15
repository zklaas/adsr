# Third-party sources

ADSR uses these open-source sources, each under its own licence.

| Source | Licence | Note |
|---|---|---|
| Loaded from the web: cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js | MPL-2.0 | recognised library (pyodide) |
| Python package PIL | MIT-CMU | Pillow is imported only by the dev tool make_icon.py (the game never imports it) and is not bundled; Pillow's licence is the HPND-style MIT-CMU licence. |
| Python package PyQt6 | GPL-3.0-only | PyQt6 is imported by app/gui.py and app/net.py and installed separately (install.sh suggests apt python3-pyqt6), not copied. Note that PyQt6 is GPL-3.0 (or commercial), so the licence chosen for ADSR should be compatible with GPL-3.0. |
