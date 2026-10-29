"""
numbering.py: PDF page numbering engine for FR-06.

Conforms to the team modifying engine contract:
    page_numbers(src, out, reporter, position, start, numerals) -> None

`numerals` is "latin" or "devanagari".
"""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pikepdf

Reporter = Callable[..., Any]

DEV_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


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


def format_page_number(
    n: int,
    total: int = 0,
    template: str = "{n}",
    numeral_system: str = "latin",
) -> str:
    """Format page number string and convert digits if devanagari."""
    text = (
        template.replace("{n}", str(n))
        .replace("{page}", str(n))
        .replace("{total}", str(total))
    )
    if numeral_system.lower() == "devanagari":
        return text.translate(DEV_DIGITS)
    return text


def get_devanagari_font_path(custom_path: Path | str | None = None) -> Path:
    """Resolve the bundled or system Noto Sans Devanagari font path."""
    if custom_path:
        p = Path(custom_path)
        if p.is_file():
            return p

    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    candidates = [
        resources_dir / "NotoSansDevanagari-Regular.ttf",
        resources_dir / "NotoSansDevanagari.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        f"Noto Sans Devanagari font not found in resources directory: {resources_dir}"
    )


def generate_page_numbers_overlay(
    page_dimensions: list[tuple[float, float]],
    page_texts: dict[int, str],
    position: str = "bottom",
    numeral_system: str = "latin",
    font_size: float = 11.0,
    margin: float = 36.0,
    font_path: Path | str | None = None,
) -> io.BytesIO:
    """Create a transparent multi-page PDF overlay containing vector page numbers."""
    from fpdf import FPDF

    fpdf = FPDF(unit="pt")
    fpdf.set_margin(0)
    fpdf.set_auto_page_break(False)

    font_family = "Helvetica"
    if numeral_system.lower() == "devanagari":
        resolved_font = get_devanagari_font_path(font_path)
        fpdf.add_font("NotoSansDevanagari", style="", fname=str(resolved_font))
        font_family = "NotoSansDevanagari"
    elif font_path:
        resolved = Path(font_path)
        if resolved.is_file():
            fpdf.add_font("CustomFont", style="", fname=str(resolved))
            font_family = "CustomFont"

    pos = position.lower().strip().replace(" ", "_").replace("-", "_")

    for idx, (w_pt, h_pt) in enumerate(page_dimensions):
        fpdf.add_page(format=(w_pt, h_pt))
        text = page_texts.get(idx)
        if not text:
            continue

        fpdf.set_font(font_family, size=font_size)
        text_w = fpdf.get_string_width(text)

        # Horizontal alignment
        if pos in (
            "bottom",
            "bottom_center",
            "bottom_centre",
            "top",
            "top_center",
            "top_centre",
        ):
            x = (w_pt - text_w) / 2.0
        elif pos in ("bottom_right", "top_right"):
            x = max(0.0, w_pt - margin - text_w)
        elif pos in ("bottom_left", "top_left"):
            x = margin
        else:
            x = (w_pt - text_w) / 2.0

        # Vertical alignment
        if pos in (
            "bottom",
            "bottom_center",
            "bottom_centre",
            "bottom_right",
            "bottom_left",
        ):
            y = max(font_size, h_pt - margin)
        else:
            y = margin + font_size

        fpdf.text(x, y, text)

    return io.BytesIO(fpdf.output())


def page_numbers(
    src: Path | str,
    out: Path | str,
    reporter: Reporter | None = None,
    position: str = "bottom",
    start: int = 1,
    numerals: str = "latin",
    pages: Sequence[int] | None = None,
    font_size: float = 11.0,
    margin: float = 36.0,
    format: str = "{n}",
    **kwargs: Any,
) -> None:
    """
    Add page numbers in Latin or Devanagari numerals to selected or all pages.

    Parameters
    ----------
    src:
        Source PDF document path.
    out:
        Output PDF destination path.
    reporter:
        Progress callback reporter.
    position:
        Placement on page: 'bottom', 'bottom_right', 'bottom_left',
        'top', 'top_right', or 'top_left'.
    start:
        Starting page number (default 1).
    numerals:
        Numeral system: 'latin' or 'devanagari'.
    pages:
        Optional sequence of 0-based page indices to number.
        If None, all pages are numbered.
    font_size:
        Font size in points (default 11.0).
    margin:
        Distance in points from the edge of the page (default 36.0 pt).
    format:
        Format string template. Supports '{n}', '{page}', and '{total}'.
    """
    src_path = Path(src)
    out_path = Path(out)
    if not src_path.is_file():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    if start < 0:
        raise ValueError("start page number must be non-negative.")
    if font_size <= 0:
        raise ValueError("font_size must be positive.")
    if margin < 0:
        raise ValueError("margin must be non-negative.")

    num_sys = (kwargs.get("numeral_system") or numerals or "latin").lower().strip()
    if num_sys not in ("latin", "devanagari"):
        raise ValueError(
            f"Unsupported numeral system: {numerals!r}. Supported options: 'latin', 'devanagari'."
        )

    pos = position.lower().strip().replace(" ", "_").replace("-", "_")
    valid_positions = {
        "bottom",
        "bottom_center",
        "bottom_centre",
        "bottom_right",
        "bottom_left",
        "top",
        "top_center",
        "top_centre",
        "top_right",
        "top_left",
    }
    if pos not in valid_positions:
        raise ValueError(
            f"Invalid position: {position!r}. Supported positions: {sorted(valid_positions)}."
        )

    _report(reporter, 0, 100, f"Adding {num_sys.title()} page numbers...")
    _check_cancelled(reporter)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with pikepdf.open(src_path) as pdf:
        total = len(pdf.pages)
        if total == 0:
            raise ValueError("Cannot number pages of an empty PDF.")

        target_pages = sorted(set(pages)) if pages is not None else list(range(total))
        if pages is not None and not target_pages:
            raise ValueError("No valid pages specified for page numbering.")

        page_texts: dict[int, str] = {}
        for seq_idx, page_idx in enumerate(target_pages):
            if 0 <= page_idx < total:
                page_texts[page_idx] = format_page_number(
                    n=start + seq_idx,
                    total=total,
                    template=format,
                    numeral_system=num_sys,
                )

        page_dimensions: list[tuple[float, float]] = []
        for page in pdf.pages:
            box = page.mediabox
            w_pt = float(box[2] - box[0])
            h_pt = float(box[3] - box[1])
            page_dimensions.append((w_pt, h_pt))

        _check_cancelled(reporter)

        font_path = kwargs.get("font_path")
        overlay_buf = generate_page_numbers_overlay(
            page_dimensions=page_dimensions,
            page_texts=page_texts,
            position=pos,
            numeral_system=num_sys,
            font_size=font_size,
            margin=margin,
            font_path=font_path,
        )

        with pikepdf.open(overlay_buf) as overlay_pdf:
            for idx, page in enumerate(pdf.pages):
                _check_cancelled(reporter)
                if idx in page_texts:
                    page.add_overlay(overlay_pdf.pages[idx])
                _report(reporter, idx + 1, total, f"Numbered page {idx + 1}/{total}")

        _check_cancelled(reporter)

        if src_path.resolve() == out_path.resolve():
            temp_out = out_path.with_name(f".{out_path.stem}.num_tmp{out_path.suffix}")
            pdf.save(temp_out)
            temp_out.replace(out_path)
        else:
            pdf.save(out_path)

    _report(reporter, total, total, "Page numbering complete")


add_page_numbers = page_numbers
