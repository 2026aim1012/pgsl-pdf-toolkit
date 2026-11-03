# pdf-toolkit.spec
# -----------------
# PyInstaller recipe for the PGSL PDF Toolkit desktop app.
#
# Build (run from the project folder, on the system you are building for):
#     uv sync --all-extras --dev
#     uv run pyinstaller pdf-toolkit.spec --noconfirm
#
# Result:
#     macOS    dist/PGSL PDF Toolkit.app          (double-click to open)
#     Windows  dist/pgsl-pdf-toolkit/pgsl-pdf-toolkit.exe
#     Linux    dist/pgsl-pdf-toolkit/pgsl-pdf-toolkit
#
# PyInstaller only builds for the system it runs on: a Mac makes the Mac
# app, Windows makes the Windows app. GitHub Actions builds all three.

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH)  # noqa: F821  (SPECPATH is provided by PyInstaller)
SRC = ROOT / "src"
RESOURCES = SRC / "pdf_toolkit" / "resources"

APP_NAME = "PGSL PDF Toolkit"  # name people see (macOS app, window title)
EXE_NAME = "pgsl-pdf-toolkit"  # file name of the program, no spaces
BUNDLE_ID = "in.ac.iitrpr.pgsl.pdftoolkit"

# Version comes from pyproject.toml, so About and the build always agree.
_match = re.search(
    r'^version\s*=\s*"([^"]+)"',
    (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
    re.MULTILINE,
)
VERSION = _match.group(1) if _match else "0.0.0"

# App icon: optional until the icons are added (Piyush, Wednesday).
# Expected files: resources/icons/app.icns (macOS), app.ico (Windows).
_icon_file = {"darwin": "app.icns", "win32": "app.ico"}.get(sys.platform)
_icon_path = RESOURCES / "icons" / _icon_file if _icon_file else None
ICON = str(_icon_path) if _icon_path and _icon_path.is_file() else None

# ---------------------------------------------------------------------------
# Files the app needs at run time that are not Python code
# ---------------------------------------------------------------------------
datas = [
    # Our own style sheet and Devanagari font. They must land in
    # pdf_toolkit/resources so the code's Path(__file__) lookups find them.
    (str(RESOURCES), "pdf_toolkit/resources"),
]
datas += collect_data_files("rapidocr_onnxruntime")  # OCR models + config.yaml
datas += collect_data_files("qtawesome")  # icon fonts
datas += collect_data_files("pypdfium2")  # version info
datas += collect_data_files("pypdfium2_raw")
datas += collect_data_files("fpdf")  # used for page numbers

binaries = []
binaries += collect_dynamic_libs("pypdfium2_raw")  # the PDFium library itself
binaries += collect_dynamic_libs("onnxruntime")  # OCR engine

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    # Things we never use; leaving them out keeps the app smaller and
    # avoids two Qt versions fighting each other.
    excludes=["tkinter", "PyQt5", "PyQt6", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # one-folder build: starts faster than one-file
    name=EXE_NAME,
    console=False,  # no black terminal window behind the app
    icon=ICON,
    upx=False,  # UPX-packed files break macOS code signing
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name=EXE_NAME,
    upx=False,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier=BUNDLE_ID,
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,  # sharp text on Retina screens
            "NSRequiresAquaSystemAppearance": False,  # follow light/dark mode
        },
    )
