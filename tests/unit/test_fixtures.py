"""
Unit tests validating all test fixtures in tests/fixtures/ and their integration
with core operations, session hub, and multilingual text handling.
"""

from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
from PIL import Image

from pdf_toolkit.core import (
    apply_watermark,
    export_text,
    images_to_pdf,
    merge_pdfs,
    pdf_to_images,
    rotate_pages,
)
from pdf_toolkit.core.page_ops import reorder_pages
from pdf_toolkit.gui.session import Session

# ── Fixture Integrity Tests ──────────────────────────────────────────


def test_english_pdf_fixture(english_pdf: Path):
    assert english_pdf.is_file()
    assert english_pdf.stat().st_size > 0

    doc = pdfium.PdfDocument(str(english_pdf))
    assert len(doc) == 3

    text0 = doc[0].get_textpage().get_text_range()
    assert "PGSL PDF Toolkit" in text0
    assert "Indian Institute of Technology Ropar" in text0

    text1 = doc[1].get_textpage().get_text_range()
    assert "Architecture & Technical Design" in text1

    text2 = doc[2].get_textpage().get_text_range()
    assert "Testing, Verification & Quality Standards" in text2

    doc.close()


def test_hindi_pdf_fixture(hindi_pdf: Path):
    assert hindi_pdf.is_file()
    assert hindi_pdf.stat().st_size > 0

    doc = pdfium.PdfDocument(str(hindi_pdf))
    assert len(doc) == 2

    text0 = doc[0].get_textpage().get_text_range()
    assert "पीजीएसएल पीडीएफ टूलकिट" in text0
    assert "भारतीय प्रौद्योगिकी संस्थान रोपड़" in text0

    text1 = doc[1].get_textpage().get_text_range()
    assert "तकनीकी संरचना" in text1

    doc.close()


def test_punjabi_pdf_fixture(punjabi_pdf: Path):
    assert punjabi_pdf.is_file()
    assert punjabi_pdf.stat().st_size > 0

    doc = pdfium.PdfDocument(str(punjabi_pdf))
    assert len(doc) == 2

    text0 = doc[0].get_textpage().get_text_range()
    assert "ਪੀਜੀਐਸਐਲ ਪੀਡੀਐਫ ਟੂਲਕਿੱਟ" in text0
    assert "ਭਾਰਤੀ ਤਕਨਾਲੋਜੀ ਸੰਸਥਾਨ ਰੋਪੜ" in text0

    text1 = doc[1].get_textpage().get_text_range()
    assert "ਤਕਨੀਕੀ ਢਾਂਚਾ" in text1

    doc.close()


def test_scanned_pdf_fixture(scanned_pdf: Path):
    assert scanned_pdf.is_file()
    assert scanned_pdf.stat().st_size > 0

    doc = pdfium.PdfDocument(str(scanned_pdf))
    assert len(doc) == 2

    # Scanned PDF should NOT have a digital text stream
    text0 = doc[0].get_textpage().get_text_range()
    text1 = doc[1].get_textpage().get_text_range()
    assert len(text0.strip()) == 0
    assert len(text1.strip()) == 0

    # Scanned PDF must contain raster image objects
    with pikepdf.open(scanned_pdf) as p:
        for page in p.pages:
            xobjects = page.Resources.get("/XObject", {})
            assert len(xobjects) > 0

    doc.close()


def test_image_fixtures(sample_images: list[Path]):
    assert len(sample_images) == 2

    img1, img2 = sample_images[0], sample_images[1]
    assert img1.is_file()
    assert img1.name == "image1.png"
    assert img2.is_file()
    assert img2.name == "image2.jpg"

    with Image.open(img1) as im1:
        assert im1.format == "PNG"
        assert im1.width == 700
        assert im1.height == 480

    with Image.open(img2) as im2:
        assert im2.format == "JPEG"
        assert im2.width == 700
        assert im2.height == 480


# ── Operations Integration Tests with Multilingual Fixtures ──────────


def test_reorder_hindi_pdf(hindi_pdf: Path, tmp_path: Path):
    out = tmp_path / "hindi_reordered.pdf"
    reorder_pages(hindi_pdf, out, order=[1, 0])

    doc = pdfium.PdfDocument(str(out))
    assert len(doc) == 2
    # Old page 2 is now first
    assert "तकनीकी संरचना" in doc[0].get_textpage().get_text_range()
    assert "पीजीएसएल पीडीएफ टूलकिट" in doc[1].get_textpage().get_text_range()
    doc.close()


def test_rotate_scanned_pdf(scanned_pdf: Path, tmp_path: Path):
    out = tmp_path / "scanned_rotated.pdf"
    rotate_pages(scanned_pdf, out, angle=90, pages=[0])

    with pikepdf.open(out) as p:
        assert int(p.pages[0].get("/Rotate", 0)) == 90
        assert int(p.pages[1].get("/Rotate", 0)) == 0


def test_merge_multilingual_pdfs(english_pdf: Path, punjabi_pdf: Path, tmp_path: Path):
    out = tmp_path / "merged_multilingual.pdf"
    merge_pdfs(None, out, files=[english_pdf, punjabi_pdf])

    doc = pdfium.PdfDocument(str(out))
    # 3 English pages + 2 Punjabi pages = 5 pages total
    assert len(doc) == 5
    assert "PGSL PDF Toolkit" in doc[0].get_textpage().get_text_range()
    assert "ਪੀਜੀਐਸਐਲ ਪੀਡੀਐਫ ਟੂਲਕਿੱਟ" in doc[3].get_textpage().get_text_range()
    doc.close()


def test_watermark_punjabi_pdf(punjabi_pdf: Path, tmp_path: Path):
    out = tmp_path / "punjabi_watermarked.pdf"
    apply_watermark(punjabi_pdf, out, text="SAMPLE", opacity=0.25)

    doc = pdfium.PdfDocument(str(out))
    assert len(doc) == 2
    # Original text is preserved under watermark
    assert "ਪੀਜੀਐਸਐਲ ਪੀਡੀਐਫ ਟੂਲਕਿੱਟ" in doc[0].get_textpage().get_text_range()
    doc.close()


def test_export_text_multilingual(hindi_pdf: Path):
    text = export_text(None, src_path=hindi_pdf)
    assert "--- Page 1 ---" in text
    assert "पीजीएसएल पीडीएफ टूलकिट" in text
    assert "--- Page 2 ---" in text
    assert "तकनीकी संरचना" in text


def test_session_lifecycle_with_hindi_fixture(qapp, hindi_pdf: Path):
    session = Session()
    assert session.open(hindi_pdf)
    assert session.page_count == 2
    assert session.page == 0

    assert session.next_page()
    assert session.page == 1

    assert session.prev_page()
    assert session.page == 0

    session.close()
    session.cleanup()


def test_images_and_pdf_roundtrip_fixtures(sample_images: list[Path], tmp_path: Path):
    pdf_out = tmp_path / "sample_images.pdf"
    images_to_pdf(None, pdf_out, None, images=sample_images)

    assert pdf_out.is_file()
    doc = pdfium.PdfDocument(str(pdf_out))
    assert len(doc) == 2
    doc.close()

    # Convert back to images
    img_out_dir = tmp_path / "extracted_images"
    extracted = pdf_to_images(None, src_path=pdf_out, out_dir=img_out_dir)
    assert len(extracted) == 2
    for img_p in extracted:
        assert img_p.is_file()
