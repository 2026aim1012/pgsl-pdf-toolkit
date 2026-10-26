"""
PDF compression engine for PGSL PDF Toolkit.

Public contract:
    compress(src, out, reporter, quality) -> None

`quality` is an integer from 1 to 100. Higher values prioritize fidelity;
lower values permit more aggressive image recompression.

The engine writes to `out` only if the result is smaller than `src`.
If compression does not reduce the file size, it preserves the original
document by copying it to `out`.

This module is deliberately independent of the GUI. It can be registered
in the application's operations dictionary, e.g.:
    {"compress": compress}
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

Reporter = Callable[..., Any]


def _report(reporter: Reporter | None, current: int, total: int, message: str) -> None:
    """Send progress updates when a reporter is supplied."""
    if reporter is not None:
        reporter(current, total, message)


def _check_cancelled(reporter: Reporter | None) -> None:
    """Honor Session cancellation when supported by the reporter."""
    check = getattr(reporter, "check_cancelled", None)
    if callable(check):
        check()


def _compress_with_pikepdf(
    src_path: Path,
    temp_path: Path,
    reporter: Reporter | None,
    quality: int,
) -> None:
    """
    Perform lossless PDF object-stream optimization with pikepdf.

    This safely removes redundant object structure and compresses PDF
    streams where possible. It does not rasterize pages or reduce image
    resolution, so quality is retained; the quality argument is accepted
    here for API compatibility and future image optimization support.
    """
    import pikepdf

    _report(reporter, 5, 100, "Opening PDF...")
    _check_cancelled(reporter)

    with pikepdf.open(src_path) as pdf:
        _check_cancelled(reporter)
        _report(reporter, 35, 100, "Optimizing PDF objects...")
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
    reporter: Reporter | None,
    quality: int = 70,
    **kwargs: Any,
) -> None:
    """
    Compress a PDF and ensure the output is never larger than the input.

    Args:
        src_path: Source PDF path.
        out_path: Destination PDF path.
        reporter: Session reporter used for progress and cancellation.
        quality: Integer 1..100; higher means higher quality.
            The initial implementation uses lossless optimization, so this
            setting is reserved for future lossy image recompression.
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
    if src.suffix.lower() != ".pdf":
        raise ValueError("Compression source must be a PDF file.")
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
            # The plan explicitly requires retaining the original if the
            # optimized result is larger or equal in size.
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
