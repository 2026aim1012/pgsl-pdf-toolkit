"""
Unit tests for FR-06 page numbering engine in pdf_toolkit.core.numbering.
"""

from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
import pytest

from pdf_toolkit.core.numbering import (
    add_page_numbers,
    format_page_number,
    get_devanagari_font_path,
    page_numbers,
)
from pdf_toolkit.core.registry import get_default_registry


class ProgressRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, str]] = []
        self.is_cancelled = False

    def __call__(self, done: int, total: int, msg: str = "") -> None:
        self.calls.append((done, total, msg))

    def check_cancelled(self) -> None:
        if self.is_cancelled:
            from pdf_toolkit.gui.session import Cancelled

            raise Cancelled("Cancelled by test")


def create_blank_pdf(
    path: Path, count: int, page_width: int = 200, page_height: int = 300
) -> Path:
    """Helper to generate a test PDF with `count` blank pages."""
    pdf = pikepdf.new()
    for _ in range(count):
        pdf.add_blank_page(page_size=(page_width, page_height))
    pdf.save(path)
    return path


def test_devanagari_font_bundled_exists():
    font_path = get_devanagari_font_path()
    assert font_path.is_file()
    assert "NotoSansDevanagari" in font_path.name


def test_format_page_number():
    assert format_page_number(1, 5, "{n}", "latin") == "1"
    assert format_page_number(42, 50, "{page} of {total}", "latin") == "42 of 50"
    assert format_page_number(1, 5, "{n}", "devanagari") == "१"
    assert format_page_number(10, 25, "{n} / {total}", "devanagari") == "१० / २५"
    assert format_page_number(3, 10, "पृष्ठ {n}", "devanagari") == "पृष्ठ ३"


def test_page_numbers_latin(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 3)
    out = tmp_path / "out_latin.pdf"
    rec = ProgressRecorder()

    page_numbers(src, out, rec, position="bottom", start=1, numerals="latin")

    assert out.is_file()
    assert len(rec.calls) >= 3

    doc = pdfium.PdfDocument(str(out))
    assert len(doc) == 3
    for i, expected in enumerate(["1", "2", "3"]):
        tp = doc[i].get_textpage()
        text = tp.get_text_range().strip()
        assert text == expected
        tp.close()
        doc[i].close()
    doc.close()


def test_page_numbers_devanagari(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 3)
    out = tmp_path / "out_dev.pdf"
    rec = ProgressRecorder()

    page_numbers(
        src, out, rec, position="bottom_right", start=1, numerals="devanagari"
    )

    assert out.is_file()
    assert len(rec.calls) >= 3

    doc = pdfium.PdfDocument(str(out))
    assert len(doc) == 3
    for i, expected in enumerate(["१", "२", "३"]):
        tp = doc[i].get_textpage()
        text = tp.get_text_range().strip()
        assert text == expected
        tp.close()
        doc[i].close()
    doc.close()


def test_page_numbers_positional_contract(tmp_path):
    # Conforms to agreed shape: op(src, out, reporter, position, start, numerals)
    src = create_blank_pdf(tmp_path / "in.pdf", 2)
    out = tmp_path / "out_positional.pdf"

    page_numbers(src, out, None, "top", 1, "devanagari")

    assert out.is_file()
    doc = pdfium.PdfDocument(str(out))
    tp = doc[0].get_textpage()
    assert tp.get_text_range().strip() == "१"
    tp.close()
    doc[0].close()
    doc.close()


def test_page_numbers_devanagari_custom_format_and_start(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 2)
    out = tmp_path / "out_format.pdf"

    add_page_numbers(
        src,
        out,
        None,
        numerals="devanagari",
        start=10,
        format="पृष्ठ {n} / {total}",
    )

    doc = pdfium.PdfDocument(str(out))
    tp0 = doc[0].get_textpage()
    assert "पृष्ठ १० / २" in tp0.get_text_range()
    tp0.close()
    doc[0].close()

    tp1 = doc[1].get_textpage()
    assert "पृष्ठ ११ / २" in tp1.get_text_range()
    tp1.close()
    doc[1].close()
    doc.close()


def test_page_numbers_specific_pages(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 4)
    out = tmp_path / "out_selective.pdf"

    page_numbers(
        src,
        out,
        None,
        numerals="devanagari",
        pages=[1, 3],
        start=1,
    )

    doc = pdfium.PdfDocument(str(out))
    tp0 = doc[0].get_textpage()
    assert tp0.get_text_range().strip() == ""
    tp0.close()
    doc[0].close()

    tp1 = doc[1].get_textpage()
    assert tp1.get_text_range().strip() == "१"
    tp1.close()
    doc[1].close()

    tp2 = doc[2].get_textpage()
    assert tp2.get_text_range().strip() == ""
    tp2.close()
    doc[2].close()

    tp3 = doc[3].get_textpage()
    assert tp3.get_text_range().strip() == "२"
    tp3.close()
    doc[3].close()
    doc.close()


def test_page_numbers_all_positions(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 1)
    positions = [
        "bottom",
        "bottom_right",
        "bottom_left",
        "top",
        "top_right",
        "top_left",
    ]
    for pos in positions:
        out = tmp_path / f"out_{pos}.pdf"
        page_numbers(src, out, None, position=pos, numerals="latin")
        assert out.is_file()


def test_page_numbers_in_place(tmp_path):
    src = create_blank_pdf(tmp_path / "in_place.pdf", 2)
    page_numbers(src, src, None, numerals="latin", start=5)

    doc = pdfium.PdfDocument(str(src))
    tp = doc[0].get_textpage()
    assert tp.get_text_range().strip() == "5"
    tp.close()
    doc[0].close()
    doc.close()


def test_page_numbers_errors(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 2)
    out = tmp_path / "out.pdf"

    with pytest.raises(FileNotFoundError):
        page_numbers(tmp_path / "missing.pdf", out)

    with pytest.raises(ValueError, match="Unsupported numeral system"):
        page_numbers(src, out, numerals="roman")

    with pytest.raises(ValueError, match="Invalid position"):
        page_numbers(src, out, position="invalid_pos")

    with pytest.raises(ValueError, match="non-negative"):
        page_numbers(src, out, start=-1)

    with pytest.raises(ValueError, match="No valid pages"):
        page_numbers(src, out, pages=[])

    empty_pdf = pikepdf.new()
    empty_path = tmp_path / "empty.pdf"
    empty_pdf.save(empty_path)
    with pytest.raises(ValueError, match="empty PDF"):
        page_numbers(empty_path, out)


def test_page_numbers_cancellation(tmp_path):
    from pdf_toolkit.gui.session import Cancelled

    src = create_blank_pdf(tmp_path / "in.pdf", 3)
    out = tmp_path / "out.pdf"
    rec = ProgressRecorder()
    rec.is_cancelled = True

    with pytest.raises(Cancelled):
        page_numbers(src, out, rec)


def test_page_numbers_registered_in_registry():
    reg = get_default_registry()
    assert "page_numbers" in reg
    assert reg["page_numbers"] is page_numbers
    info = reg.get_info("page_numbers")
    assert info.is_modifying
    assert info.name == "page_numbers"
