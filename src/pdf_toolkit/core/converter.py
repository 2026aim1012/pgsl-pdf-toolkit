"""Image <-> PDF conversion (FR-04, FR-05)."""
from pathlib import Path
import os, tempfile
import img2pdf
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
    raise NotImplementedError