"""
operations.py: Built-in PDF operations for PGSL PDF Toolkit.

Follows the team backend contract:
- Modifying operations:
    op(src: Path | str, out: Path | str, reporter: Reporter | None, **opts) -> None
- Read-only operations:
    fn(reporter: Reporter | None, src_path: Path | str | None = None, **kwargs) -> Any
"""

from __future__ import annotations

import io
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pikepdf
from PIL import Image, ImageDraw, ImageFont

from pdf_toolkit.core.converter import (
    images_to_pdf as _converter_images_to_pdf,
)
from pdf_toolkit.core.converter import (
    pdf_to_images as _converter_pdf_to_images,
)
from pdf_toolkit.core.page_ops import insert_pages, reorder_pages

if TYPE_CHECKING:
    from pdf_toolkit.core.registry import OperationsRegistry

Reporter = Callable[..., Any]


def _report(reporter: Reporter | None, done: int, total: int, msg: str = "") -> None:
    """Send progress update if reporter is supplied."""
    if reporter is not None:
        reporter(done, total, msg)


def _check_cancelled(reporter: Reporter | None) -> None:
    """Raise Cancelled if user requested cancellation."""
    if reporter is not None:
        check = getattr(reporter, "check_cancelled", None)
        if callable(check):
            check()
        elif getattr(reporter, "is_cancelled", False):
            from pdf_toolkit.gui.session import Cancelled

            raise Cancelled("Operation cancelled by user")


class _NullReporter:
    """Safe no-op reporter passed to core converter functions when reporter is None."""

    def __call__(self, done: int, total: int, msg: str = "") -> None:
        pass

    def set_message(self, msg: str) -> None:
        pass

    def check_cancelled(self) -> None:
        pass


# ── Modifying Operations ─────────────────────────────────────────────


def rotate_pages(
    src: Path | str,
    out: Path | str,
    reporter: Reporter | None = None,
    angle: int = 90,
    pages: Sequence[int] | None = None,
    **kwargs: Any,
) -> None:
    """Rotate selected (or all) pages by angle degrees clockwise."""
    src_path = Path(src)
    out_path = Path(out)
    if not src_path.is_file():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    _report(reporter, 0, 100, f"Rotating pages by {angle}°...")
    _check_cancelled(reporter)

    with pikepdf.open(src_path) as pdf:
        total = len(pdf.pages)
        target = set(pages) if pages is not None else set(range(total))
        for idx, page in enumerate(pdf.pages):
            _check_cancelled(reporter)
            if idx in target:
                cur = int(page.get("/Rotate", 0))
                page.Rotate = (cur + angle) % 360
            _report(reporter, idx + 1, total, f"Rotated page {idx + 1}/{total}")

        _check_cancelled(reporter)
        pdf.save(out_path)

    _report(reporter, 100, 100, "Rotation complete")


def reverse_pages(
    src: Path | str,
    out: Path | str,
    reporter: Reporter | None = None,
    **kwargs: Any,
) -> None:
    """Reverse the page order of the document."""
    src_path = Path(src)
    out_path = Path(out)
    if not src_path.is_file():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    _report(reporter, 0, 100, "Reversing page order...")
    _check_cancelled(reporter)

    with pikepdf.open(src_path) as pdf:
        _check_cancelled(reporter)
        pdf.pages.reverse()
        _check_cancelled(reporter)
        pdf.save(out_path)

    _report(reporter, 100, 100, "Pages reversed")


def delete_pages(
    src: Path | str,
    out: Path | str,
    reporter: Reporter | None = None,
    pages: Sequence[int] | None = None,
    **kwargs: Any,
) -> None:
    """Delete selected 0-based pages from the document."""
    src_path = Path(src)
    out_path = Path(out)
    if not src_path.is_file():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    target_pages = sorted(set(pages or []))
    if not target_pages:
        raise ValueError("No pages specified for deletion.")

    _report(reporter, 0, 100, f"Deleting {len(target_pages)} page(s)...")
    _check_cancelled(reporter)

    with pikepdf.open(src_path) as pdf:
        if len(target_pages) >= len(pdf.pages):
            raise ValueError("Cannot delete all pages from the document.")

        for idx in sorted(target_pages, reverse=True):
            _check_cancelled(reporter)
            if 0 <= idx < len(pdf.pages):
                del pdf.pages[idx]

        _check_cancelled(reporter)
        pdf.save(out_path)

    _report(reporter, 100, 100, "Pages deleted")


def merge_pdfs(
    src: Path | str | None,
    out: Path | str,
    reporter: Reporter | None = None,
    files: Sequence[Path | str] | None = None,
    **kwargs: Any,
) -> None:
    """Merge two or more PDFs into a single output document."""
    out_path = Path(out)
    merge_files = [Path(f) for f in (files or [])]
    if len(merge_files) < 2:
        raise ValueError("At least 2 files required to merge.")

    for f in merge_files:
        if not f.is_file():
            raise FileNotFoundError(f"File to merge not found: {f}")

    _report(reporter, 0, len(merge_files), "Merging files...")
    _check_cancelled(reporter)

    merged = pikepdf.new()
    for idx, f in enumerate(merge_files):
        _check_cancelled(reporter)
        with pikepdf.open(f) as p:
            merged.pages.extend(p.pages)
        _report(reporter, idx + 1, len(merge_files), f"Merged {f.name}")

    _check_cancelled(reporter)
    merged.save(out_path)
    _report(reporter, len(merge_files), len(merge_files), "Merge complete")


def _create_watermark_buffer(
    width_pt: float,
    height_pt: float,
    text: str,
    opacity: float = 0.3,
    rotation: float = 45.0,
) -> io.BytesIO:
    """Create a transparent 1-page PDF stream containing centered rotated watermark text."""
    scale = 2.0
    w_px = max(50, int(width_pt * scale))
    h_px = max(50, int(height_pt * scale))

    txt_canvas_size = max(w_px, h_px) * 2
    txt_im = Image.new("RGBA", (txt_canvas_size, txt_canvas_size), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt_im)

    alpha = int(max(0.01, min(1.0, opacity)) * 255)
    font_size = max(14, int(min(w_px, h_px) / 10))

    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
    ]
    loaded = False
    for fp in font_paths:
        if Path(fp).is_file():
            try:
                font = ImageFont.truetype(fp, font_size)
                loaded = True
                break
            except OSError:
                continue
    if not loaded:
        font = ImageFont.load_default()

    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, cy = txt_canvas_size // 2, txt_canvas_size // 2
    d.text((cx - tw // 2, cy - th // 2), text, fill=(100, 100, 100, alpha), font=font)

    rotated = txt_im.rotate(rotation, resample=Image.Resampling.BILINEAR)
    crop_x = (rotated.width - w_px) // 2
    crop_y = (rotated.height - h_px) // 2
    cropped = rotated.crop((crop_x, crop_y, crop_x + w_px, crop_y + h_px))

    buf = io.BytesIO()
    cropped.save(buf, format="PDF", resolution=72.0 * scale)
    buf.seek(0)
    return buf


def apply_watermark(
    src: Path | str,
    out: Path | str,
    reporter: Reporter | None = None,
    text: str = "",
    opacity: float = 0.3,
    rotation: float = 45.0,
    pages: Sequence[int] | None = None,
    **kwargs: Any,
) -> None:
    """Apply a text watermark overlay to selected (or all) pages."""
    src_path = Path(src)
    out_path = Path(out)
    if not src_path.is_file():
        raise FileNotFoundError(f"Source file not found: {src_path}")
    if not text.strip():
        raise ValueError("Watermark text cannot be empty.")

    _report(reporter, 0, 100, "Applying watermark...")
    _check_cancelled(reporter)

    with pikepdf.open(src_path) as pdf:
        total = len(pdf.pages)
        target = set(pages) if pages is not None else set(range(total))

        for idx, page in enumerate(pdf.pages):
            _check_cancelled(reporter)
            if idx in target:
                box = page.mediabox
                w_pt = float(box[2] - box[0])
                h_pt = float(box[3] - box[1])
                wm_buf = _create_watermark_buffer(
                    width_pt=w_pt,
                    height_pt=h_pt,
                    text=text,
                    opacity=opacity,
                    rotation=rotation,
                )
                with pikepdf.open(wm_buf) as wm_pdf:
                    page.add_overlay(wm_pdf.pages[0])

            _report(reporter, idx + 1, total, f"Watermarked page {idx + 1}/{total}")

        _check_cancelled(reporter)
        pdf.save(out_path)

    _report(reporter, 100, 100, "Watermark applied")


def compress_pdf(
    src_path: Path | str,
    out_path: Path | str,
    reporter: Reporter | None = None,
    quality: int = 70,
    **kwargs: Any,
) -> None:
    """
    Compress PDF streams and optimize objects.
    Ensures output is never larger than the input.
    """
    src = Path(src_path).resolve()
    out = Path(out_path).resolve()

    if not src.is_file():
        raise FileNotFoundError(f"Source file not found: {src}")
    if not 1 <= int(quality) <= 100:
        raise ValueError("quality must be between 1 and 100.")
    if src == out:
        raise ValueError("Source and destination must be different files.")

    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(f".{out.stem}.comp_tmp{out.suffix}")
    if temp.exists():
        temp.unlink()

    src_size = src.stat().st_size
    _report(reporter, 10, 100, "Optimizing PDF streams...")
    _check_cancelled(reporter)

    try:
        with pikepdf.open(src) as pdf:
            _check_cancelled(reporter)
            pdf.save(
                temp,
                compress_streams=True,
                recompress_flate=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )

        _check_cancelled(reporter)
        if not temp.is_file():
            raise RuntimeError("Compression failed to produce output file.")

        compressed_size = temp.stat().st_size
        if compressed_size < src_size:
            temp.replace(out)
            _report(
                reporter,
                100,
                100,
                f"Compressed: {src_size} -> {compressed_size} bytes",
            )
        else:
            temp.unlink(missing_ok=True)
            shutil.copy2(src, out)
            _report(reporter, 100, 100, "Original size retained (already optimal)")
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def images_to_pdf(
    src: Any = None,
    out: Any = None,
    reporter: Any = None,
    *,
    images: Sequence[Path | str] | None = None,
    files: Sequence[Path | str] | None = None,
    **kwargs: Any,
) -> Path:
    """
    Convert a sequence of images into a PDF document.

    Conforms to modifying contract: op(src, out, reporter, **opts) -> Path
    Also accepts direct call convention: op(reporter, images, out_path).
    """
    if isinstance(out, (list, tuple)):
        actual_reporter = src
        actual_images = out
        actual_out = reporter or kwargs.get("out_path") or kwargs.get("out")
    elif isinstance(src, (list, tuple)):
        actual_images = src
        actual_out = out or kwargs.get("out_path") or kwargs.get("out")
        actual_reporter = reporter or kwargs.get("reporter")
    else:
        actual_out = out or kwargs.get("out") or kwargs.get("out_path")
        actual_reporter = reporter or kwargs.get("reporter")
        actual_images = images or files or kwargs.get("picked_files")

    if actual_out is None:
        raise ValueError("Output path must be specified.")
    if not actual_images:
        raise ValueError("No images selected")

    rep = actual_reporter if actual_reporter is not None else _NullReporter()
    return _converter_images_to_pdf(rep, actual_images, actual_out)


# ── Read-only Operations ─────────────────────────────────────────────


def export_text(
    reporter: Reporter | None = None,
    src_path: Path | str | None = None,
    **kwargs: Any,
) -> str:
    """Extract plain text from all pages of the document."""
    import pypdfium2 as pdfium

    if not src_path or not Path(src_path).is_file():
        return "(No document open to extract text from.)"

    src = Path(src_path)
    _report(reporter, 0, 100, "Extracting text...")
    _check_cancelled(reporter)

    doc = pdfium.PdfDocument(str(src))
    texts: list[str] = []
    total = len(doc)
    for i, page in enumerate(doc):
        _check_cancelled(reporter)
        textpage = page.get_textpage()
        page_text = textpage.get_text_range()
        textpage.close()
        page.close()
        texts.append(f"--- Page {i + 1} ---\n{page_text}")
        _report(reporter, i + 1, total, f"Extracted page {i + 1}/{total}")

    doc.close()
    return "\n\n".join(texts)


def ocr_document(
    reporter: Reporter | None = None,
    src_path: Path | str | None = None,
    **kwargs: Any,
) -> str:
    """Run OCR text recognition (using RapidOCR with fallback)."""
    if not src_path or not Path(src_path).is_file():
        return "(No document open for OCR.)"

    src = Path(src_path)
    try:
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(src))
        results: list[str] = []
        total = len(doc)
        _report(reporter, 0, total, "Initializing OCR engine...")
        _check_cancelled(reporter)

        for i, page in enumerate(doc):
            _check_cancelled(reporter)
            pil_image = page.render(scale=2.0).to_pil()
            page.close()
            ocr_res, _ = engine(pil_image)
            lines = [line[1] for line in ocr_res] if ocr_res else []
            results.append(f"--- Page {i + 1} ---\n" + "\n".join(lines))
            _report(reporter, i + 1, total, f"OCR on page {i + 1}/{total}")

        doc.close()
        return "\n\n".join(results)
    except Exception:  # noqa: BLE001
        return export_text(reporter, src_path=src, **kwargs)


def pdf_to_images(
    reporter: Reporter | None = None,
    pdf: Path | str | None = None,
    out_dir: Path | str | None = None,
    dpi: int = 150,
    *,
    src_path: Path | str | None = None,
    **kwargs: Any,
) -> list[Path]:
    """
    Convert PDF pages into individual image files (PNG).

    Conforms to read-only contract: fn(reporter=None, src_path=..., out_dir=..., dpi=150) -> list[Path]
    Also accepts direct call convention: fn(reporter, pdf, out_dir, dpi=150).
    """
    target_pdf = pdf if pdf is not None else (src_path or kwargs.get("src"))
    if not target_pdf:
        raise ValueError("No PDF document specified.")

    target_out_dir = out_dir if out_dir is not None else kwargs.get("out_dir")
    if not target_out_dir:
        raise ValueError("out_dir must be specified.")

    target_dpi = dpi if dpi is not None else kwargs.get("dpi", 150)
    rep = reporter if reporter is not None else _NullReporter()

    return _converter_pdf_to_images(rep, target_pdf, target_out_dir, dpi=target_dpi)


# ── Registration Helper ──────────────────────────────────────────────


def register_default_operations(registry: OperationsRegistry) -> None:
    """Register all standard PDF Toolkit operations into the given registry."""
    registry.register(
        "rotate",
        rotate_pages,
        kind="modifying",
        display_name="Rotate Pages",
        description="Rotate selected pages by specified degrees (e.g. 90, 180, 270).",
    )
    registry.register(
        "reverse",
        reverse_pages,
        kind="modifying",
        display_name="Reverse Order",
        description="Reverse page sequence across the entire document.",
    )
    registry.register(
        "delete",
        delete_pages,
        kind="modifying",
        display_name="Delete Pages",
        description="Delete specified pages from the document.",
    )
    registry.register(
        "merge",
        merge_pdfs,
        kind="modifying",
        display_name="Merge PDFs",
        description="Merge two or more PDF files into a single document.",
    )
    registry.register(
        "watermark",
        apply_watermark,
        kind="modifying",
        display_name="Watermark",
        description="Apply custom text watermark with configurable opacity and rotation.",
    )
    registry.register(
        "reorder",
        reorder_pages,
        kind="modifying",
        display_name="Reorder Pages",
        description="Reorder pages according to a specified sequence.",
    )
    registry.register(
        "insert",
        insert_pages,
        kind="modifying",
        display_name="Insert Pages",
        description="Insert pages from another PDF file into the document.",
    )
    registry.register(
        "compress",
        compress_pdf,
        kind="modifying",
        display_name="Compress PDF",
        description="Losslessly compress PDF streams and remove redundant objects.",
    )
    registry.register(
        "export_text",
        export_text,
        kind="read_only",
        display_name="Export Text",
        description="Extract raw textual contents from all document pages.",
    )
    registry.register(
        "ocr",
        ocr_document,
        kind="read_only",
        display_name="Run OCR",
        description="Perform optical character recognition to extract text from scanned pages.",
    )
    registry.register(
        "images_to_pdf",
        images_to_pdf,
        kind="modifying",
        display_name="Images to PDF",
        description="Convert multiple image files into a single PDF document.",
    )
    registry.register(
        "image_to_pdf",
        images_to_pdf,
        kind="modifying",
        display_name="Images to PDF",
        description="Convert multiple image files into a single PDF document.",
    )
    registry.register(
        "pdf_to_images",
        pdf_to_images,
        kind="read_only",
        display_name="PDF to Images",
        description="Convert PDF pages into individual image files (PNG).",
    )
