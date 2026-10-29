"""
PDF compression engine for PGSL PDF Toolkit.

Public contract:
    compress(src, out, reporter, quality) -> None

`quality` is an integer from 1 to 100 (the Toolkit slider).

What compression does, in two steps:

1. Photos inside the PDF are re-saved as JPEG at the chosen quality.
   Lower quality = smaller file, slightly softer photos.
   A photo is only replaced when the new version is actually smaller.
   At quality 100 this step is skipped, so nothing is lost.
2. The PDF structure is tidied up without losing anything
   (streams compressed, objects packed together).

The engine never makes a file bigger: if the result is not smaller than
the input, the original is copied to `out` unchanged.

This module is independent of the GUI and is registered as "compress"
in core/operations.py.
"""

from __future__ import annotations

import io
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

Reporter = Callable[..., Any]

# Colour spaces we know how to save as JPEG without changing the colours.
_JPEG_SAFE_COLORSPACES = {"/DeviceRGB": "RGB", "/DeviceGray": "L"}

# Filters (encodings) we leave alone: special formats for scans and
# black-and-white images, where JPEG would make things worse.
_SKIP_FILTERS = {"/JPXDecode", "/CCITTFaxDecode", "/JBIG2Decode"}


def _report(reporter: Reporter | None, current: int, total: int, message: str) -> None:
    """Send progress updates when a reporter is supplied."""
    if reporter is not None:
        reporter(current, total, message)


def _check_cancelled(reporter: Reporter | None) -> None:
    """Honor Session cancellation when supported by the reporter."""
    check = getattr(reporter, "check_cancelled", None)
    if callable(check):
        check()


def _filters_of(image: Any) -> list[str]:
    """Return the image's filter names as a list, e.g. ["/FlateDecode"]."""
    import pikepdf

    raw = image.get("/Filter")
    if raw is None:
        return []
    if isinstance(raw, pikepdf.Array):  # several filters, e.g. [/A85 /Flate]
        return [str(f) for f in raw]
    return [str(raw)]


def _can_recompress(image: Any) -> bool:
    """True if this image is a plain 8-bit RGB or grey photo we can safely re-save."""
    if image.get("/ImageMask", False):
        return False  # a stencil mask, not a picture
    if "/Decode" in image:
        return False  # colours are remapped; JPEG would get them wrong
    if int(image.get("/BitsPerComponent", 0)) != 8:
        return False
    if str(image.get("/ColorSpace", "")) not in _JPEG_SAFE_COLORSPACES:
        return False
    return not any(f in _SKIP_FILTERS for f in _filters_of(image))


def _recompress_images(pdf: Any, quality: int, reporter: Reporter | None) -> int:
    """
    Re-save the photos on every page as JPEG at `quality`.

    Returns how many images were replaced. Images used on several pages
    are only processed once.
    """
    import pikepdf

    seen: set[tuple[int, int]] = set()
    replaced = 0
    total = len(pdf.pages)

    for page_number, page in enumerate(pdf.pages, start=1):
        _check_cancelled(reporter)
        _report(
            reporter,
            10 + int(60 * page_number / max(total, 1)),
            100,
            f"Compressing images on page {page_number}/{total}...",
        )

        for image in page.images.values():
            key = image.objgen
            if key in seen:
                continue
            seen.add(key)

            if not _can_recompress(image):
                continue

            try:
                picture = pikepdf.PdfImage(image).as_pil_image()
            except Exception:  # noqa: BLE001, S112 - undecodable images are left as they are
                continue

            mode = _JPEG_SAFE_COLORSPACES[str(image.ColorSpace)]
            if picture.mode != mode:
                picture = picture.convert(mode)

            buffer = io.BytesIO()
            picture.save(buffer, format="JPEG", quality=quality, optimize=True)
            new_bytes = buffer.getvalue()

            # Only swap in the JPEG if it really is smaller.
            if len(new_bytes) >= len(image.read_raw_bytes()):
                continue

            image.write(new_bytes, filter=pikepdf.Name.DCTDecode)
            if "/DecodeParms" in image:
                del image["/DecodeParms"]
            replaced += 1

            picture.close()  # free the memory used by the decoded picture

    return replaced


def _compress_with_pikepdf(
    src_path: Path,
    temp_path: Path,
    reporter: Reporter | None,
    quality: int,
) -> None:
    """Write a compressed copy of `src_path` to `temp_path`."""
    import pikepdf

    _report(reporter, 5, 100, "Opening PDF...")
    _check_cancelled(reporter)

    with pikepdf.open(src_path) as pdf:
        if quality < 100:
            _recompress_images(pdf, quality, reporter)

        _check_cancelled(reporter)
        _report(reporter, 75, 100, "Optimizing PDF objects...")
        pdf.save(
            temp_path,
            compress_streams=True,
            recompress_flate=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )

    _check_cancelled(reporter)
    _report(reporter, 90, 100, "Checking compressed output...")


def compress(
    src_path: str | Path,
    out_path: str | Path,
    reporter: Reporter | None = None,
    quality: int = 70,
    **kwargs: Any,
) -> None:
    """
    Compress a PDF and ensure the output is never larger than the input.

    Args:
        src_path: Source PDF path.
        out_path: Destination PDF path.
        reporter: Session reporter used for progress and cancellation.
        quality: Integer 1..100; higher means better-looking photos.
            100 keeps every image exactly as it is.
        **kwargs: Accepted for compatibility with Session.apply.

    Raises:
        FileNotFoundError: Source PDF does not exist.
        ValueError: Invalid quality or source/destination are the same file.
        RuntimeError: PDF processing fails.
    """
    src = Path(src_path).expanduser().resolve()
    out = Path(out_path).expanduser().resolve()

    if not src.is_file():
        raise FileNotFoundError(f"Source PDF not found: {src}")
    if not 1 <= int(quality) <= 100:
        raise ValueError("quality must be between 1 and 100.")

    quality = int(quality)
    if src == out:
        raise ValueError("Source and output paths must be different.")

    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(f".{out.stem}.compressing{out.suffix}")

    # Avoid a stale temporary file being mistaken for a new result.
    if temp.exists():
        temp.unlink()

    source_size = src.stat().st_size
    _report(reporter, 0, 100, f"Compressing PDF (quality {quality})...")
    _check_cancelled(reporter)

    try:
        _compress_with_pikepdf(src, temp, reporter, quality)
        _check_cancelled(reporter)

        if not temp.is_file():
            raise RuntimeError("Compression did not produce an output file.")

        compressed_size = temp.stat().st_size
        if compressed_size < source_size:
            # Atomic replace prevents a partial destination file.
            temp.replace(out)
            _report(
                reporter,
                100,
                100,
                f"Compression complete: {source_size} -> {compressed_size} bytes.",
            )
        else:
            # Never make the file bigger: keep the original.
            temp.unlink(missing_ok=True)
            shutil.copy2(src, out)
            _report(
                reporter,
                100,
                100,
                "No size reduction; original PDF retained.",
            )
    except Exception:
        temp.unlink(missing_ok=True)
        raise


# Compatibility alias if a registry prefers the more explicit name.
compress_pdf = compress
