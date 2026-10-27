"""Image <-> PDF conversion (FR-04, FR-05)."""
import os
import tempfile
from pathlib import Path

import img2pdf
import pypdfium2 as pdfium
from PIL import Image


def _progress(reporter, done, total, msg=""):
    reporter(done, total, msg)

def _flatten(path, tmpdir):
    """PNGs with transparency make img2pdf fail; flatten them onto white."""
    img = Image.open(path)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.split()[-1])
        out = Path(tmpdir) / (Path(path).stem + "_flat.jpg")
        bg.save(out, quality=95)
        return str(out)
    return str(path)

def images_to_pdf(reporter, images, out_path) -> Path:
    images = [Path(p) for p in images]
    if not images:
        raise ValueError("No images selected")
    out_path = Path(out_path)
    part = out_path.with_suffix(".pdf.part")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            files = []
            for i, p in enumerate(images):
                _progress(reporter, i, len(images), f"Reading {p.name}")
                files.append(_flatten(p, tmp))
            reporter.set_message("Writing PDF…")
            part.write_bytes(img2pdf.convert(files))
            reporter.check_cancelled()
            os.replace(part, out_path)  # fearless save
    finally:
        part.unlink(missing_ok=True)  # no half-written file on cancel/error
    _progress(reporter, len(images), len(images), f"Created {out_path.name}")
    return out_path

def pdf_to_images(reporter, pdf, out_dir, dpi=150) -> list[Path]:
    pdf, out_dir = Path(pdf), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf))
    try:
        total = len(doc)
        results = []
        for i in range(total):
            _progress(reporter, i, total, f"Saving page {i + 1}/{total}")
            img = doc[i].render(scale=dpi / 72).to_pil()
            out = out_dir / f"{pdf.stem}_page{i + 1:03d}.png"
            img.save(out)
            results.append(out)
        return results
    finally:
        doc.close()