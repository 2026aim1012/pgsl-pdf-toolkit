"""
check_build.py
--------------
Checks a PyInstaller build after `uv run pyinstaller pdf-toolkit.spec`.

    uv run python packaging/check_build.py          # check files and size
    uv run python packaging/check_build.py --run    # also start the app once

It answers three questions:
1. Did the files the app needs at run time make it into the build?
2. How big is the build?
3. (with --run) Does the app start and stay open, or crash straight away?

It exits with code 0 when everything is fine and 1 when something is
missing, so the GitHub build workflow can use it too.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
APP_NAME = "PGSL PDF Toolkit"
EXE_NAME = "pgsl-pdf-toolkit"

# File name patterns that must exist somewhere inside the build.
REQUIRED = {
    "style sheet": ["style.qss"],
    "Devanagari font": ["NotoSansDevanagari-Regular.ttf"],
    "PDFium library (page rendering)": [
        "pdfium.dll",
        "libpdfium.dylib",
        "libpdfium.so",
    ],
    "OCR models": ["*.onnx"],
}


def find_build() -> tuple[Path, Path]:
    """Return (folder to measure, program to start) for this system's build."""
    if sys.platform == "darwin":
        app = DIST / f"{APP_NAME}.app"
        return app, app / "Contents" / "MacOS" / EXE_NAME
    folder = DIST / EXE_NAME
    program = folder / (EXE_NAME + (".exe" if sys.platform == "win32" else ""))
    return folder, program


def size_mb(folder: Path) -> float:
    """Total size of all real files in `folder`, in megabytes."""
    total = sum(
        f.stat().st_size
        for f in folder.rglob("*")
        if f.is_file() and not f.is_symlink()
    )
    return total / (1024 * 1024)


def check_files(folder: Path) -> list[str]:
    """Return the names of required items that are missing from the build."""
    missing = []
    for label, patterns in REQUIRED.items():
        if not any(next(folder.rglob(p), None) for p in patterns):
            missing.append(label)
    return missing


def try_start(program: Path, seconds: int = 10) -> bool:
    """Start the app; it passes if it is still running after `seconds`."""
    env = dict(os.environ)
    if sys.platform.startswith("linux") and not env.get("DISPLAY"):
        env["QT_QPA_PLATFORM"] = "offscreen"  # no screen (e.g. on GitHub)
    print(f"Starting {program.name} for {seconds} seconds...")
    proc = subprocess.Popen(
        [str(program)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env
    )
    time.sleep(seconds)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("OK   the app started and stayed open")
        return True
    output = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
    print(f"FAIL the app closed by itself (exit code {proc.returncode})")
    print("---- its output (paste this into the GitHub issue) ----")
    print(output.strip() or "(no output)")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", action="store_true", help="also start the app once")
    args = parser.parse_args()

    folder, program = find_build()
    if not folder.exists():
        print(f"FAIL no build found at {folder}")
        print("     Run first:  uv run pyinstaller pdf-toolkit.spec --noconfirm")
        return 1

    print(f"Build:  {folder}")
    print(f"System: {sys.platform}")
    print(f"Size:   {size_mb(folder):.0f} MB")

    ok = True
    missing = check_files(folder)
    for label in REQUIRED:
        status = "MISSING" if label in missing else "OK     "
        print(f"{status} {label}")
    ok = ok and not missing

    if not program.is_file():
        print(f"FAIL program not found: {program}")
        return 1

    if args.run:
        ok = try_start(program) and ok

    print("\nAll checks passed." if ok else "\nSome checks failed; see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
