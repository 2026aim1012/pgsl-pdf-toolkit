"""
Unit tests for standard core operations in pdf_toolkit.core.operations.
"""

from pathlib import Path

import pikepdf
import pytest

from pdf_toolkit.core.operations import (
    apply_watermark,
    compress_pdf,
    delete_pages,
    export_text,
    merge_pdfs,
    reverse_pages,
    rotate_pages,
)


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


# ── Rotate ────────────────────────────────────────────────────────────


def test_rotate_all_pages(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 3)
    out = tmp_path / "out.pdf"
    rec = ProgressRecorder()

    rotate_pages(src, out, rec, angle=90)

    assert out.is_file()
    with pikepdf.open(out) as p:
        assert len(p.pages) == 3
        for page in p.pages:
            assert int(page.get("/Rotate", 0)) == 90
    assert len(rec.calls) > 0


def test_rotate_specific_pages(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 4)
    out = tmp_path / "out.pdf"

    rotate_pages(src, out, None, angle=180, pages=[1, 3])

    with pikepdf.open(out) as p:
        assert int(p.pages[0].get("/Rotate", 0)) == 0
        assert int(p.pages[1].get("/Rotate", 0)) == 180
        assert int(p.pages[2].get("/Rotate", 0)) == 0
        assert int(p.pages[3].get("/Rotate", 0)) == 180


def test_rotate_missing_src_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        rotate_pages(tmp_path / "missing.pdf", tmp_path / "out.pdf", None)


# ── Reverse ───────────────────────────────────────────────────────────


def test_reverse_pages(tmp_path):
    src = tmp_path / "in.pdf"
    pdf = pikepdf.new()
    for w in [100, 200, 300]:
        pdf.add_blank_page(page_size=(w, 400))
    pdf.save(src)
    out = tmp_path / "out.pdf"

    reverse_pages(src, out, None)

    with pikepdf.open(out) as p:
        widths = [int(page.mediabox[2]) for page in p.pages]
        assert widths == [300, 200, 100]

    # Check source left untouched
    with pikepdf.open(src) as p:
        widths = [int(page.mediabox[2]) for page in p.pages]
        assert widths == [100, 200, 300]


# ── Delete ────────────────────────────────────────────────────────────


def test_delete_pages(tmp_path):
    src = tmp_path / "in.pdf"
    pdf = pikepdf.new()
    for w in [100, 200, 300, 400]:
        pdf.add_blank_page(page_size=(w, 500))
    pdf.save(src)
    out = tmp_path / "out.pdf"

    delete_pages(src, out, None, pages=[1, 3])

    with pikepdf.open(out) as p:
        widths = [int(page.mediabox[2]) for page in p.pages]
        assert widths == [100, 300]


def test_delete_all_pages_fails(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 2)
    out = tmp_path / "out.pdf"

    with pytest.raises(ValueError, match="Cannot delete all pages"):
        delete_pages(src, out, None, pages=[0, 1])


def test_delete_no_pages_fails(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 2)
    out = tmp_path / "out.pdf"

    with pytest.raises(ValueError, match="No pages specified"):
        delete_pages(src, out, None, pages=[])


# ── Merge ─────────────────────────────────────────────────────────────


def test_merge_pdfs(tmp_path):
    f1 = create_blank_pdf(tmp_path / "f1.pdf", 2)
    f2 = create_blank_pdf(tmp_path / "f2.pdf", 3)
    out = tmp_path / "out.pdf"
    rec = ProgressRecorder()

    merge_pdfs(None, out, rec, files=[f1, f2])

    assert out.is_file()
    with pikepdf.open(out) as p:
        assert len(p.pages) == 5
    assert len(rec.calls) >= 2


def test_merge_fewer_than_two_files_fails(tmp_path):
    f1 = create_blank_pdf(tmp_path / "f1.pdf", 2)
    out = tmp_path / "out.pdf"

    with pytest.raises(ValueError, match="At least 2 files required"):
        merge_pdfs(None, out, None, files=[f1])


# ── Watermark ─────────────────────────────────────────────────────────


def test_apply_watermark(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 2)
    out = tmp_path / "out.pdf"
    rec = ProgressRecorder()

    apply_watermark(src, out, rec, text="CONFIDENTIAL", opacity=0.3, rotation=45.0)

    assert out.is_file()
    with pikepdf.open(out) as p:
        assert len(p.pages) == 2
        assert "/Contents" in p.pages[0]
        assert len(bytes(p.pages[0].Contents)) > 0


def test_apply_watermark_empty_text_fails(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 2)
    out = tmp_path / "out.pdf"

    with pytest.raises(ValueError, match="Watermark text cannot be empty"):
        apply_watermark(src, out, None, text="   ")


# ── Compress ──────────────────────────────────────────────────────────


def test_compress_pdf(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 5)
    out = tmp_path / "out.pdf"
    rec = ProgressRecorder()

    compress_pdf(src, out, rec, quality=75)

    assert out.is_file()
    assert out.stat().st_size <= src.stat().st_size


def test_compress_same_file_fails(tmp_path):
    src = create_blank_pdf(tmp_path / "in.pdf", 2)
    with pytest.raises(ValueError, match="must be different"):
        compress_pdf(src, src, None)


# ── Export Text ───────────────────────────────────────────────────────


def test_export_text_nonexistent():
    result = export_text(None, src_path=Path("/tmp/nonexistent.pdf"))
    assert "No document open" in result
