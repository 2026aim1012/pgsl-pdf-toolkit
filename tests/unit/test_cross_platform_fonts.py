"""Text must be sized in pixels so it fits its boxes on every system.

Bug seen on Windows: the style sheet sized text in points (12pt) and boxes in
pixels. Qt draws 12pt as 12 px on macOS (72 dpi) but as 16 px on Windows
(96 dpi), so on Windows text was a third bigger than the boxes made for it
and got cut off ("Entire document", "Delete Selected Pages", "ages -> P").
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESOURCES = ROOT / "src" / "pdf_toolkit" / "resources"
POINT_SIZE = re.compile(r"font-size:\s*[\d.]+\s*pt", re.IGNORECASE)


def test_style_sheets_size_text_in_pixels():
    for sheet in ("style.qss", "style_dark.qss"):
        text = (RESOURCES / sheet).read_text(encoding="utf-8")
        assert not POINT_SIZE.search(text), f"{sheet} uses a point size"


def test_python_code_sizes_fonts_in_pixels():
    for path in (ROOT / "src" / "pdf_toolkit").rglob("*.py"):
        code = path.read_text(encoding="utf-8")
        assert "setPointSize(" not in code, f"{path.name} uses setPointSize"
        assert not POINT_SIZE.search(code), f"{path.name} uses a point size"
