import pikepdf
import pypdfium2 as pdfium
import pytest
from PIL import Image
from pdf_toolkit.core.converter import images_to_pdf, pdf_to_images

class FakeReporter:
    def __call__(self, done, total, msg=""): pass
    def set_message(self, msg): pass
    def check_cancelled(self): pass

def make_img(path, color, mode="RGB"):
    Image.new(mode, (200, 300), color).save(path)
    return path

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
    assert blue > r                      # first page is blue

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