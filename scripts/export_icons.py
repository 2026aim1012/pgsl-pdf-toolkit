"""Developer utility to export icons from QtAwesome into static resource PNGs.

Usage:
    python scripts/export_icons.py fa5s.print print.png
    python scripts/export_icons.py fa5s.moon moon.png --color "#334155" --size 24
    python scripts/export_icons.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import qtawesome as qta
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QApplication
except ImportError:
    print(
        "Error: 'qtawesome' and 'PySide6' are required dev dependencies.\n"
        "Install them with: uv sync",
        file=sys.stderr,
    )
    sys.exit(1)

ICONS_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "pdf_toolkit"
    / "resources"
    / "icons"
)

# Registry of standard icons used across the application
DEFAULT_ICONS: dict[str, tuple[str, str]] = {
    "moon.png": ("fa5s.moon", "#334155"),
    "sun.png": ("fa5s.sun", "#d97706"),
    "file-pdf.png": ("fa5s.file-pdf", "#2563eb"),
    "folder-open.png": ("fa5s.folder-open", "#2563eb"),
    "save.png": ("fa5s.save", "#2563eb"),
    "save-as.png": ("fa5s.file-export", "#2563eb"),
    "close.png": ("fa5s.times-circle", "#64748b"),
    "exit.png": ("fa5s.sign-out-alt", "#64748b"),
    "undo.png": ("fa5s.undo", "#2563eb"),
    "chevron-left.png": ("fa5s.chevron-left", "#475569"),
    "chevron-right.png": ("fa5s.chevron-right", "#475569"),
    "panel-explorer.png": ("fa5s.columns", "#2563eb"),
    "panel-toolkit.png": ("fa5s.tools", "#2563eb"),
    "reset-layout.png": ("fa5s.th-large", "#2563eb"),
    "keyboard.png": ("fa5s.keyboard", "#2563eb"),
    "info.png": ("fa5s.info-circle", "#2563eb"),
}


def export_icon(
    icon_name: str,
    output_filename: str,
    color: str = "#2563eb",
    size: int = 24,
) -> Path:
    """Export a single QtAwesome icon to the resources/icons directory."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    if not output_filename.endswith(".png"):
        output_filename = f"{output_filename}.png"

    output_path = ICONS_DIR / output_filename
    icon = qta.icon(icon_name, color=color)
    pixmap = icon.pixmap(QSize(size, size))
    pixmap.save(str(output_path), "PNG")
    print(
        f"Exported: {icon_name} -> {output_path.relative_to(Path.cwd())} ({size}x{size}, {color})"
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export QtAwesome icons to static PNGs in resources/icons"
    )
    parser.add_argument(
        "icon_name",
        nargs="?",
        help="QtAwesome icon identifier (e.g. 'fa5s.print', 'msc.file')",
    )
    parser.add_argument(
        "output_filename",
        nargs="?",
        help="Destination filename in resources/icons (e.g. 'print.png')",
    )
    parser.add_argument(
        "--color",
        default="#2563eb",
        help="Icon fill color (default: #2563eb)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=24,
        help="Icon dimension in pixels (default: 24)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Export all default icons configured in DEFAULT_ICONS",
    )

    args = parser.parse_args()

    # Ensure a QApplication instance exists for Qt rendering
    _ = QApplication.instance() or QApplication(sys.argv)

    if args.all:
        print(f"Exporting all default icons to {ICONS_DIR}...")
        for filename, (icon_name, color) in DEFAULT_ICONS.items():
            export_icon(icon_name, filename, color=color, size=args.size)
        print("Done exporting all default icons.")
        return

    if not args.icon_name:
        parser.print_help()
        sys.exit(1)

    filename = args.output_filename or f"{args.icon_name.split('.')[-1]}.png"
    export_icon(args.icon_name, filename, color=args.color, size=args.size)


if __name__ == "__main__":
    main()
