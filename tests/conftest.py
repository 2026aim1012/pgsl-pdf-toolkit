import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

# Run headless in test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Ensure src and src/pdf_toolkit/gui are in sys.path
root_dir = Path(__file__).resolve().parent.parent
gui_dir = root_dir / "src" / "pdf_toolkit" / "gui"
for p in [str(root_dir / "src"), str(gui_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Path to the tests/fixtures directory."""
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def english_pdf(fixtures_dir: Path) -> Path:
    """Path to English 3-page test PDF."""
    return fixtures_dir / "english.pdf"


@pytest.fixture(scope="session")
def hindi_pdf(fixtures_dir: Path) -> Path:
    """Path to Hindi (Devanagari) 2-page test PDF."""
    return fixtures_dir / "hindi.pdf"


@pytest.fixture(scope="session")
def punjabi_pdf(fixtures_dir: Path) -> Path:
    """Path to Punjabi (Gurmukhi) 2-page test PDF."""
    return fixtures_dir / "punjabi.pdf"


@pytest.fixture(scope="session")
def scanned_pdf(fixtures_dir: Path) -> Path:
    """Path to scanned image-only 2-page test PDF."""
    return fixtures_dir / "scanned.pdf"


@pytest.fixture(scope="session")
def sample_images(fixtures_dir: Path) -> list[Path]:
    """Paths to the two sample images (PNG and JPG)."""
    return [fixtures_dir / "image1.png", fixtures_dir / "image2.jpg"]
