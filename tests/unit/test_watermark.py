"""
The watermark must be clearly visible on every computer.

Bug found on a Mac: the code only looked for Linux font files, fell back to
Pillow's 10-pixel default font, and the watermark became a tiny smudge.
These tests render the watermarked page and count how much of it is covered.
"""

from pathlib import Path

import pikepdf
import pypdfium2 as pdfium

import pdf_toolkit.core.operations as ops


def blank_pdf(path: Path) -> Path:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(595, 842))  # A4 in points
    pdf.save(path)
    return path


def covered_fraction(path: Path) -> float:
    """Share of the page's pixels that are not white."""
    doc = pdfium.PdfDocument(str(path))
    image = doc[0].render(scale=0.5).to_pil().convert("L")
    doc.close()
    pixels = list(image.getdata())
    return sum(1 for p in pixels if p < 250) / len(pixels)


def test_watermark_visible_without_system_fonts(tmp_path, monkeypatch):
    """Like a Mac without the Linux fonts: still a big, readable watermark."""
    monkeypatch.setattr(ops, "_WATERMARK_FONTS", [tmp_path / "missing.ttf"])
    src = blank_pdf(tmp_path / "in.pdf")
    out = tmp_path / "out.pdf"

    ops.apply_watermark(src, out, None, text="hello world", opacity=0.3)

    # The old bug covered about 0.1% of the page; a real watermark covers far more.
    assert covered_fraction(out) > 0.01


def test_long_watermark_stays_on_the_page(tmp_path):
    """A long text is shrunk to fit, so nothing is drawn near the page edges."""
    text = "CONFIDENTIAL DRAFT - DO NOT SHARE OUTSIDE THE OFFICE"
    src = blank_pdf(tmp_path / "in.pdf")
    out = tmp_path / "out.pdf"

    ops.apply_watermark(src, out, None, text=text, opacity=0.5, rotation=45)

    doc = pdfium.PdfDocument(str(out))
    image = doc[0].render(scale=0.5).to_pil().convert("L")
    doc.close()
    w, h = image.size
    edge = int(min(w, h) * 0.05)  # a 5% strip around the page
    for x, y in [(x, y) for x in range(w) for y in range(h)]:
        if x < edge or y < edge or x >= w - edge or y >= h - edge:
            assert image.getpixel((x, y)) >= 250, f"text reaches the edge at {x},{y}"
    assert covered_fraction(out) > 0.005


def test_hindi_watermark_uses_devanagari_font():
    assert ops._has_devanagari("गोपनीय")
    assert not ops._has_devanagari("hello")
    font = ops._watermark_font("गोपनीय", 40)
    assert "Devanagari" in font.getname()[0]
