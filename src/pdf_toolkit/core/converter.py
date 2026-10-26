"""Image <-> PDF conversion (FR-04, FR-05)."""
from pathlib import Path

def images_to_pdf(reporter, images, out_path) -> Path:
    raise NotImplementedError

def pdf_to_images(reporter, pdf, out_dir, dpi=150) -> list[Path]:
    raise NotImplementedError