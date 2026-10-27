import pikepdf
import pypdfium2 as pdfium
import pytest
from PIL import Image

from pdf_toolkit.core.converter import images_to_pdf, pdf_to_images
from pdf_toolkit.gui.session import Cancelled


# Helpers
class FakeReporter:
    def __call__(self, done, total, msg=""):
        pass

    def set_message(self, msg):
        pass

    def check_cancelled(self):
        pass


class CancelAfterFirstReporter(FakeReporter):
    """Simulates the user pressing Cancel while the second image is read."""

    def __call__(self, done, total, msg=""):
        if done >= 1:
            raise Cancelled("Operation cancelled by user")


def make_img(path, color, mode="RGB"):
    Image.new(mode, (200, 300), color).save(path)
    return path


def make_pdf(path, pages=3):
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(100, 100))
    pdf.save(path)
    return path


# images_to_pdf (FR-04)


def test_images_to_pdf_page_count(tmp_path):
    a = make_img(tmp_path / "a.png", "red")
    b = make_img(tmp_path / "b.png", "blue")
    out = images_to_pdf(FakeReporter(), [a, b], tmp_path / "out.pdf")
    assert len(pdfium.PdfDocument(str(out))) == 2


def test_images_to_pdf_keeps_order(tmp_path):
    a = make_img(tmp_path / "a.png", "red")
    b = make_img(tmp_path / "b.png", "blue")
    out = images_to_pdf(FakeReporter(), [b, a], tmp_path / "out.pdf")
    first = pdfium.PdfDocument(str(out))[0].render(scale=0.2).to_pil().convert("RGB")
    r, _, blue = first.getpixel((5, 5))
    assert blue > r  # first page is blue


def test_transparent_png(tmp_path):
    t = make_img(tmp_path / "t.png", (255, 0, 0, 0), "RGBA")
    out = images_to_pdf(FakeReporter(), [t], tmp_path / "t.pdf")
    assert out.exists()


def test_no_part_file_left_behind(tmp_path):
    a = make_img(tmp_path / "a.png", "red")
    images_to_pdf(FakeReporter(), [a], tmp_path / "out.pdf")
    assert not list(tmp_path.glob("*.part"))


def test_empty_list_raises(tmp_path):
    with pytest.raises(ValueError):
        images_to_pdf(FakeReporter(), [], tmp_path / "x.pdf")


def test_cancel_leaves_no_partial_file(tmp_path):
    a = make_img(tmp_path / "a.png", "red")
    with pytest.raises(Cancelled):
        images_to_pdf(CancelAfterFirstReporter(), [a, a], tmp_path / "out.pdf")
    assert not (tmp_path / "out.pdf").exists()
    assert not list(tmp_path.glob("*.part"))


# pdf_to_images (FR-05)


def test_pdf_to_images_names_and_count(tmp_path):
    pdf = make_pdf(tmp_path / "doc.pdf")
    files = pdf_to_images(FakeReporter(), pdf, tmp_path / "out", dpi=72)
    assert [f.name for f in files] == [
        "doc_page001.png",
        "doc_page002.png",
        "doc_page003.png",
    ]
    assert all(f.exists() for f in files)


def test_pdf_to_images_dpi_changes_size(tmp_path):
    pdf = make_pdf(tmp_path / "doc.pdf", pages=1)
    lo = Image.open(pdf_to_images(FakeReporter(), pdf, tmp_path / "lo", 72)[0]).size
    hi = Image.open(pdf_to_images(FakeReporter(), pdf, tmp_path / "hi", 144)[0]).size
    assert hi[0] == lo[0] * 2


def test_pdf_to_images_creates_output_folder(tmp_path):
    pdf = make_pdf(tmp_path / "doc.pdf", pages=1)
    out_dir = tmp_path / "new" / "nested"
    pdf_to_images(FakeReporter(), pdf, out_dir, dpi=72)
    assert out_dir.is_dir()
