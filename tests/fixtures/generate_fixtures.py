"""
generate_fixtures.py
--------------------
Utility script to create authentic test fixtures in tests/fixtures/:
  - english.pdf  (3-page English digital PDF)
  - hindi.pdf    (2-page Hindi Devanagari digital PDF)
  - punjabi.pdf  (2-page Punjabi Gurmukhi digital PDF)
  - scanned.pdf  (2-page scanned image-only PDF with no digital text layer)
  - image1.png   (Architecture diagram / UI preview test image)
  - image2.jpg   (Document card / photographic sample test image)
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

FIXTURES_DIR = Path(__file__).resolve().parent
FONTS_DIR = Path("/tmp/pdf_toolkit_fonts")

FONT_URLS = {
    "NotoSansDevanagari-Regular.ttf": (
        "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/"
        "NotoSansDevanagari/NotoSansDevanagari-Regular.ttf"
    ),
    "NotoSansGurmukhi-Regular.ttf": (
        "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/"
        "NotoSansGurmukhi/NotoSansGurmukhi-Regular.ttf"
    ),
}


def ensure_font(filename: str) -> Path:
    """Ensure Noto font is available in FONTS_DIR and return path."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    target = FONTS_DIR / filename
    if target.is_file():
        return target
    tmp_candidate = Path("/tmp") / filename
    if tmp_candidate.is_file():
        import shutil
        shutil.copy2(tmp_candidate, target)
        return target
    import subprocess
    url = FONT_URLS[filename]
    subprocess.run(["curl", "-sL", "-A", "Mozilla/5.0", url, "-o", str(target)], check=True)
    return target


def get_default_font(size: int = 14) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
    ]:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


# ── 1. English PDF ───────────────────────────────────────────────────

def build_english_pdf(out_path: Path) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Page 1
    pdf.add_page()
    pdf.set_font("helvetica", "B", 20)
    pdf.cell(w=pdf.epw, h=14, text="PGSL PDF Toolkit", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("helvetica", "I", 12)
    pdf.cell(w=pdf.epw, h=8, text="Indian Institute of Technology Ropar", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    pdf.set_font("helvetica", "B", 14)
    pdf.cell(w=pdf.epw, h=10, text="1. Executive Summary & Overview", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(
        w=pdf.epw,
        h=6,
        text=(
            "The PGSL PDF Toolkit is a lightweight, responsive desktop application developed for "
            "comprehensive PDF document management. Designed to meet academic and professional "
            "standards at IIT Ropar, the system combines high-performance PDF manipulation with an "
            "intuitive three-panel graphical user interface.\n\n"
            "Key capabilities include non-destructive page rotation, reordering, deletion, insertion, "
            "merging, watermark application, plain text extraction, and optical character recognition (OCR)."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    pdf.set_font("helvetica", "B", 14)
    pdf.cell(w=pdf.epw, h=10, text="2. Core Requirements", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    requirements = [
        "FR-01: Document preview with responsive thumbnail strip and navigation.",
        "FR-02: Page-level manipulation (reorder, rotate, delete, insert).",
        "FR-03: Multi-document batch processing (merge PDFs, image to PDF).",
        "FR-04: Advanced tools (watermark overlay, compression, plain text export).",
        "FR-05: Integrated OCR for scanned documents across Indic and English scripts.",
    ]
    for req in requirements:
        pdf.multi_cell(w=pdf.epw, h=6, text=f"- {req}", new_x="LMARGIN", new_y="NEXT")

    # Page 2
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(w=pdf.epw, h=12, text="Architecture & Technical Design", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(
        w=pdf.epw,
        h=6,
        text=(
            "The toolkit architecture strictly decouples graphical user interface components from "
            "core document processing engines. The system is composed of four principal subsystems:\n\n"
            "1. Explorer Panel (Left): Directory navigation, file tree representation, and multi-file "
            "selection for batch operations.\n\n"
            "2. Preview Panel (Center): High-fidelity rendering via pypdfium2, smooth zooming, and "
            "thumbnail-based page selection with multi-select support.\n\n"
            "3. Toolkit Panel (Right): Vertically stacked control groups providing accessible action "
            "buttons, numerical spinboxes, and parameter sliders.\n\n"
            "4. Session Hub & Worker: Central signal-driven communication coordinator ensuring panels "
            "never directly depend on one another. Long-running operations execute asynchronously in "
            "dedicated worker threads, providing non-blocking responsiveness and cancel support."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    # Page 3
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(w=pdf.epw, h=12, text="Testing, Verification & Quality Standards", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(
        w=pdf.epw,
        h=6,
        text=(
            "All modifications undergo automated verification using pytest and ruff. Tests are run "
            "in headless offscreen environments (QT_QPA_PLATFORM=offscreen) to enable seamless continuous "
            "integration on server instances.\n\n"
            "Key quality standards:\n"
            "- Complete preservation of original document files (immutable working copy model).\n"
            "- Undo stack supporting history traversal of the last 10 applied operations.\n"
            "- Progress reporting with user cancellation checkpoints at every processing cycle.\n"
            "- Robust exception handling for encrypted, corrupted, or unsupported media formats."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.output(str(out_path))


# ── 2. Hindi PDF ─────────────────────────────────────────────────────

def build_hindi_pdf(out_path: Path) -> None:
    deva_font = ensure_font("NotoSansDevanagari-Regular.ttf")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("NotoDeva", fname=str(deva_font))

    # Page 1
    pdf.add_page()
    pdf.set_font("NotoDeva", size=18)
    pdf.cell(w=pdf.epw, h=14, text="पीजीएसएल पीडीएफ टूलकिट", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("NotoDeva", size=12)
    pdf.cell(w=pdf.epw, h=8, text="भारतीय प्रौद्योगिकी संस्थान रोपड़ - संगणक विज्ञान विभाग", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    pdf.set_font("NotoDeva", size=14)
    pdf.cell(w=pdf.epw, h=10, text="१. सारांश एवं परिचय", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoDeva", size=10)
    pdf.multi_cell(
        w=pdf.epw,
        h=7,
        text=(
            "पीजीएसएल पीडीएफ टूलकिट एक शक्तिशाली और आधुनिक सॉफ्टवेयर है जो पीडीएफ फाइलों के संपादन, "
            "पुनर्गठन और प्रबंधन के लिए तैयार किया गया है। यह टूलकिट मुख्य रूप से भारतीय प्रौद्योगिकी संस्थान "
            "रोपड़ के छात्रों, शोधकर्ताओं और प्राध्यापकों की आवश्यकताओं को ध्यान में रखकर बनाया गया है।\n\n"
            "इस प्रणाली में पृष्ठों को घुमाना, पृष्ठों का क्रम बदलना, पृष्ठ हटाना, "
            "कई दस्तावेजों को एक साथ जोड़ना, जलचिह्न जोड़ना और ऑप्टिकल कैरेक्टर रिकॉग्निशन (ओसीआर) "
            "की संपूर्ण सुविधाएं उपलब्ध हैं।"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    pdf.set_font("NotoDeva", size=14)
    pdf.cell(w=pdf.epw, h=10, text="२. मुख्य विशेषताएं", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoDeva", size=10)
    items = [
        "दस्तावेज़ सुरक्षा: मूल फ़ाइल कभी भी सीधे संशोधित नहीं होती।",
        "असीमित पूर्ववत: पिछले कार्यों को तुरंत रद्द करने की सुविधा।",
        "बहुभाषी समर्थन: हिंदी, पंजाबी और अंग्रेजी दस्तावेजों के लिए पूर्ण समर्थन।",
        "तीव्र गति: बैकग्राउंड थ्रेड्स द्वारा निर्बाध कार्य निष्पादन।",
    ]
    for it in items:
        pdf.multi_cell(w=pdf.epw, h=7, text=f"- {it}", new_x="LMARGIN", new_y="NEXT")

    # Page 2
    pdf.add_page()
    pdf.set_font("NotoDeva", size=16)
    pdf.cell(w=pdf.epw, h=12, text="तकनीकी संरचना एवं मॉड्यूल", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoDeva", size=10)
    pdf.multi_cell(
        w=pdf.epw,
        h=7,
        text=(
            "टूलकिट को त्रि-स्तरीय संरचना पर आधारित किया गया है:\n\n"
            "१. एक्सप्लोरर पैनल (बायाँ): कंप्यूटर में मौजूद फोल्डर और फाइलों को देखना एवं बैच प्रोसेसिंग के लिए चुनना।\n\n"
            "२. पूर्वावलोकन पैनल (मध्य): वर्तमान पृष्ठ को उच्च गुणवत्ता में प्रदर्शित करना और थंबनेल पट्टी द्वारा त्वरित नेविगेशन।\n\n"
            "३. टूलकिट पैनल (दायाँ): सभी संपादन टूल्स, जैसे रोटेशन, डिलीट, मर्ज, और ओसीआर का नियंत्रण केंद्र।\n\n"
            "४. सत्र नियंत्रक: सभी घटकों के मध्य सिग्नल द्वारा तालमेल बनाना जिससे सॉफ्टवेयर तेज और स्थिर रहे।"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.output(str(out_path))


# ── 3. Punjabi PDF ───────────────────────────────────────────────────

def build_punjabi_pdf(out_path: Path) -> None:
    guru_font = ensure_font("NotoSansGurmukhi-Regular.ttf")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("NotoGuru", fname=str(guru_font))

    # Page 1
    pdf.add_page()
    pdf.set_font("NotoGuru", size=18)
    pdf.cell(w=pdf.epw, h=14, text="ਪੀਜੀਐਸਐਲ ਪੀਡੀਐਫ ਟੂਲਕਿੱਟ", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("NotoGuru", size=12)
    pdf.cell(w=pdf.epw, h=8, text="ਭਾਰਤੀ ਤਕਨਾਲੋਜੀ ਸੰਸਥਾਨ ਰੋਪੜ - ਕੰਪਿਊਟਰ ਸਾਇੰਸ ਵਿਭਾਗ", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    pdf.set_font("NotoGuru", size=14)
    pdf.cell(w=pdf.epw, h=10, text="੧. ਜਾਣ-ਪਛਾਣ ਅਤੇ ਉਦੇਸ਼", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoGuru", size=10)
    pdf.multi_cell(
        w=pdf.epw,
        h=7,
        text=(
            "ਪੀਜੀਐਸਐਲ ਪੀਡੀਐਫ ਟੂਲਕਿੱਟ ਆਈਆਈਟੀ ਰੋਪੜ ਵਿਖੇ ਵਿਕਸਤ ਕੀਤਾ ਗਿਆ ਇੱਕ ਆਧੁਨਿਕ ਅਤੇ ਤੇਜ਼ ਦਸਤਾਵੇਜ਼ ਪ੍ਰਬੰਧਨ ਸਿਸਟਮ ਹੈ। "
            "ਇਸ ਸਾਫਟਵੇਅਰ ਦਾ ਮੁੱਖ ਮਕਸਦ ਵਿਦਿਆਰਥੀਆਂ ਅਤੇ ਖੋਜੀਆਂ ਨੂੰ ਪੀਡੀਐਫ ਫਾਈਲਾਂ ਦਾ ਸੰਪਾਦਨ ਕਰਨ ਲਈ ਇੱਕ ਸੁਵਿਧਾਜਨਕ ਪਲੇਟਫਾਰਮ "
            "ਮੁਹੱਈਆ ਕਰਵਾਉਣਾ ਹੈ।\n\n"
            "ਇਸ ਟੂਲਕਿੱਟ ਰਾਹੀਂ ਪੰਨਿਆਂ ਨੂੰ ਘੁਮਾਉਣਾ, ਕ੍ਰਮ ਬਦਲਣਾ, ਨਵੇਂ ਪੰਨੇ ਜੋੜਨਾ, ਬੇਲੋੜੇ ਪੰਨੇ ਹਟਾਉਣਾ ਅਤੇ ਸਕੈਨ ਕੀਤੇ "
            "ਦਸਤਾਵੇਜ਼ਾਂ ਵਿੱਚੋਂ ਲਿਖਤ ਕੱਢਣ (ਓਸੀਆਰ) ਦੀਆਂ ਸੁਵਿਧਾਵਾਂ ਉਪਲਬਧ ਹਨ।"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    pdf.set_font("NotoGuru", size=14)
    pdf.cell(w=pdf.epw, h=10, text="੨. ਮੁੱਖ ਵਿਸ਼ੇਸ਼ਤਾਵਾਂ", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoGuru", size=10)
    items = [
        "ਮੂਲ ਫਾਈਲ ਦੀ ਸੁਰੱਖਿਆ: ਅਸਲ ਫਾਈਲ ਨੂੰ ਕਦੇ ਵੀ ਸਿੱਧਾ ਨਹੀਂ ਬਦਲਿਆ ਜਾਂਦਾ।",
        "ਅਨਡੂ ਸੁਵਿਧਾ: ਗਲਤੀ ਨਾਲ ਹੋਏ ਬਦਲਾਅ ਨੂੰ ਤੁਰੰਤ ਵਾਪਸ ਲਿਆ ਜਾ ਸਕਦਾ ਹੈ।",
        "ਗੁਰਮੁਖੀ ਲਿਪੀ ਸਮਰਥਨ: ਪੰਜਾਬੀ ਦਸਤਾਵੇਜ਼ਾਂ ਨੂੰ ਪੜ੍ਹਨ ਅਤੇ ਸੰਭਾਲਣ ਦੀ ਸਮਰੱਥਾ।",
        "ਤੇਜ਼ ਕਾਰਗੁਜ਼ਾਰੀ: ਪਾਈਥਨ ਅਤੇ ਕਿਊਟੀ ਦੀ ਵਰਤੋਂ ਨਾਲ ਸੁਚਾਰੂ ਕਾਰਜ।",
    ]
    for it in items:
        pdf.multi_cell(w=pdf.epw, h=7, text=f"- {it}", new_x="LMARGIN", new_y="NEXT")

    # Page 2
    pdf.add_page()
    pdf.set_font("NotoGuru", size=16)
    pdf.cell(w=pdf.epw, h=12, text="ਤਕਨੀਕੀ ਢਾਂਚਾ ਅਤੇ ਸੰਚਾਲਨ", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoGuru", size=10)
    pdf.multi_cell(
        w=pdf.epw,
        h=7,
        text=(
            "ਇਸ ਐਪਲੀਕੇਸ਼ਨ ਨੂੰ ਚਾਰ ਪ੍ਰਮੁੱਖ ਹਿੱਸਿਆਂ ਵਿੱਚ ਵੰਡਿਆ ਗਿਆ ਹੈ:\n\n"
            "੧. ਐਕਸਪਲੋਰਰ ਪੈਨਲ: ਫੋਲਡਰ ਖੋਲ੍ਹਣ ਅਤੇ ਫਾਈਲਾਂ ਦੀ ਚੋਣ ਕਰਨ ਲਈ ਖੱਬਾ ਪੈਨਲ।\n\n"
            "੨. ਪ੍ਰੀਵਿਊ ਪੈਨਲ: ਪੀਡੀਐਫ ਦੇ ਪੰਨਿਆਂ ਨੂੰ ਸਾਫ਼ ਤਰੀਕੇ ਨਾਲ ਦਿਖਾਉਣ ਲਈ ਵਿਚਕਾਰਲਾ ਪੈਨਲ।\n\n"
            "੩. ਟੂਲਕਿੱਟ ਪੈਨਲ: ਸਾਰੇ ਓਪਰੇਸ਼ਨ ਬਟਨਾਂ (ਰੋਟੇਟ, ਡਿਲੀਟ, ਮਰਜ) ਲਈ ਸੱਜਾ ਪੈਨਲ।\n\n"
            "੪. ਸੈਸ਼ਨ ਹੱਬ: ਸਾਰੇ ਪੈਨਲਾਂ ਵਿੱਚ ਸੰਪਰਕ ਬਣਾਉਣ ਵਾਲਾ ਕੇਂਦਰੀ ਕੰਟਰੋਲਰ।"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.output(str(out_path))


# ── 4. Scanned PDF (Image-only, no digital text layer) ───────────────

def build_scanned_pdf(out_path: Path) -> None:
    font = get_default_font(size=18)
    font_bold = get_default_font(size=22)
    font_small = get_default_font(size=14)

    w, h = 850, 1150

    # Scanned Page 1: Official Department Invoice
    im1 = Image.new("RGB", (w, h), (248, 248, 245))
    d1 = ImageDraw.Draw(im1)
    # Outer frame
    d1.rectangle([(30, 30), (w - 30, h - 30)], outline=(160, 160, 160), width=2)
    # Header box
    d1.rectangle([(40, 40), (w - 40, 130)], fill=(235, 238, 242), outline=(140, 140, 150))
    d1.text((60, 55), "INDIAN INSTITUTE OF TECHNOLOGY ROPAR", fill=(20, 20, 20), font=font_bold)
    d1.text((60, 95), "Department of Computer Science & Engineering - Equipment Invoice", fill=(60, 60, 60), font=font_small)

    d1.text((60, 160), "Invoice ID: IITRPR-CS509-2026-081", fill=(30, 30, 30), font=font)
    d1.text((60, 200), "Date of Issue: 26 October 2026", fill=(30, 30, 30), font=font)
    d1.text((60, 240), "Vendor: Advanced Computing Lab Supplies Ltd.", fill=(30, 30, 30), font=font)
    d1.text((60, 280), "Billing Account: Project Grant PGSL-CS509", fill=(30, 30, 30), font=font)

    # Table Header
    d1.rectangle([(50, 330), (w - 50, 370)], fill=(220, 225, 230), outline=(150, 150, 150))
    d1.text((70, 340), "Item No.", fill=(20, 20, 20), font=font_small)
    d1.text((180, 340), "Description", fill=(20, 20, 20), font=font_small)
    d1.text((550, 340), "Quantity", fill=(20, 20, 20), font=font_small)
    d1.text((680, 340), "Total (INR)", fill=(20, 20, 20), font=font_small)

    rows = [
        ("01", "High-Resolution Document Scanner 600DPI", "2", "38,000.00"),
        ("02", "Optical Character Recognition Test Unit", "1", "15,500.00"),
        ("03", "Offline Verification & Storage Modules", "4", "12,000.00"),
        ("04", "Calibration Standards Chart & Sheet Set", "1", "4,500.00"),
    ]
    y = 380
    for r in rows:
        d1.text((70, y), r[0], fill=(40, 40, 40), font=font_small)
        d1.text((180, y), r[1], fill=(40, 40, 40), font=font_small)
        d1.text((580, y), r[2], fill=(40, 40, 40), font=font_small)
        d1.text((680, y), r[3], fill=(40, 40, 40), font=font_small)
        y += 40
        d1.line([(50, y - 5), (w - 50, y - 5)], fill=(210, 210, 210))

    d1.rectangle([(50, 580), (w - 50, 630)], fill=(240, 245, 240), outline=(120, 160, 120))
    d1.text((70, 595), "Total Payable: INR 70,000.00", fill=(20, 80, 20), font=font_bold)
    d1.text((70, 660), "Status: VERIFIED AND APPROVED BY AUDIT COMMITTEE", fill=(100, 30, 30), font=font_small)

    # Scanned Page 2: Lab Audit & Inspection Certificate
    im2 = Image.new("RGB", (w, h), (250, 249, 246))
    d2 = ImageDraw.Draw(im2)
    d2.rectangle([(30, 30), (w - 30, h - 30)], outline=(160, 160, 160), width=2)
    d2.rectangle([(40, 40), (w - 40, 130)], fill=(245, 240, 235), outline=(150, 140, 130))
    d2.text((60, 55), "LABORATORY AUDIT & COMPLIANCE REPORT", fill=(20, 20, 20), font=font_bold)
    d2.text((60, 95), "Certificate of Compliance - Semester 1, Academic Year 2026-2027", fill=(60, 60, 60), font=font_small)

    d2.text((60, 160), "Inspection Reference: AUDIT-COMP-2026-Q3", fill=(30, 30, 30), font=font)
    d2.text((60, 200), "Facility: PGSL Research Laboratory, Room 304", fill=(30, 30, 30), font=font)
    d2.text((60, 240), "Audited Systems: 12 Workstations, 2 Scanner Stations", fill=(30, 30, 30), font=font)

    d2.text((60, 300), "Audit Findings:", fill=(20, 20, 20), font=font)
    findings = [
        "1. All scanning hardware calibrated to ISO standard tolerances.",
        "2. Optical character recognition tests passed with >98% accuracy.",
        "3. Multi-language font rendering confirmed for English, Hindi, and Punjabi.",
        "4. Non-destructive working copy model validated against data integrity standards.",
    ]
    fy = 340
    for finding in findings:
        d2.text((80, fy), finding, fill=(50, 50, 50), font=font_small)
        fy += 45

    d2.text((60, 560), "Authorized Signatory: Head of Department", fill=(20, 20, 20), font=font)
    d2.text((60, 600), "Signature Date: 26-10-2026", fill=(60, 60, 60), font=font_small)

    im1.save(out_path, format="PDF", save_all=True, append_images=[im2])


# ── 5. Images ────────────────────────────────────────────────────────

def build_images(out_png: Path, out_jpg: Path) -> None:
    font = get_default_font(size=16)
    font_bold = get_default_font(size=20)
    font_small = get_default_font(size=12)

    # Image 1 (PNG): Architecture Overview Diagram
    w, h = 700, 480
    im1 = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    d1 = ImageDraw.Draw(im1)

    # Title Banner
    d1.rounded_rectangle([(20, 20), (w - 20, 75)], radius=8, fill=(35, 55, 95))
    d1.text((40, 35), "PGSL PDF Toolkit Architecture Diagram", fill=(255, 255, 255), font=font_bold)

    # Box 1: Explorer Panel
    d1.rounded_rectangle([(40, 110), (220, 270)], radius=6, fill=(240, 244, 250), outline=(70, 110, 180), width=2)
    d1.text((55, 125), "Explorer Panel", fill=(20, 40, 90), font=font)
    d1.text((55, 160), "- File Browsing\n- Folder Select\n- Batch Pick", fill=(60, 60, 60), font=font_small)

    # Box 2: Preview Panel
    d1.rounded_rectangle([(260, 110), (440, 270)], radius=6, fill=(245, 250, 245), outline=(60, 150, 80), width=2)
    d1.text((275, 125), "Preview Panel", fill=(20, 90, 40), font=font)
    d1.text((275, 160), "- Page Render\n- Thumbnails\n- Multi-select", fill=(60, 60, 60), font=font_small)

    # Box 3: Toolkit Panel
    d1.rounded_rectangle([(480, 110), (660, 270)], radius=6, fill=(253, 245, 245), outline=(200, 80, 80), width=2)
    d1.text((495, 125), "Toolkit Panel", fill=(120, 30, 30), font=font)
    d1.text((495, 160), "- Rotate / Reverse\n- Merge / Delete\n- Watermark / OCR", fill=(60, 60, 60), font=font_small)

    # Session Hub Box
    d1.rounded_rectangle([(140, 320), (560, 440)], radius=8, fill=(248, 240, 255), outline=(130, 70, 190), width=2)
    d1.text((230, 335), "Session Hub & Background Worker", fill=(70, 30, 120), font=font)
    d1.text((160, 375), "- Non-destructive temp copies   - Undo stack (max 10)\n- Qt signals communication          - Cancellation support", fill=(60, 60, 60), font=font_small)

    # Connective arrows
    d1.line([(130, 270), (220, 320)], fill=(100, 100, 100), width=2)
    d1.line([(350, 270), (350, 320)], fill=(100, 100, 100), width=2)
    d1.line([(570, 270), (480, 320)], fill=(100, 100, 100), width=2)

    im1.save(out_png, format="PNG")

    # Image 2 (JPG): Sample Certificate Card
    w2, h2 = 700, 480
    im2 = Image.new("RGB", (w2, h2), (245, 242, 235))
    d2 = ImageDraw.Draw(im2)

    # Border
    d2.rectangle([(25, 25), (w2 - 25, h2 - 25)], outline=(180, 150, 90), width=3)
    d2.rectangle([(35, 35), (w2 - 35, h2 - 35)], outline=(210, 190, 140), width=1)

    # Title
    d2.text((120, 70), "INDIAN INSTITUTE OF TECHNOLOGY ROPAR", fill=(80, 50, 20), font=font_bold)
    d2.text((220, 115), "Course CS509 - Software Engineering", fill=(100, 80, 50), font=font)

    d2.text((160, 175), "Certificate of Test Fixture Verification", fill=(40, 40, 40), font=font_bold)
    d2.text(
        (80, 230),
        "This sample document image serves as a visual verification asset for\n"
        "Explorer directory browsing, image-to-PDF batch compilation, and\n"
        "optical character recognition accuracy benchmarks.",
        fill=(50, 50, 50),
        font=font,
    )

    d2.line([(80, 350), (300, 350)], fill=(150, 130, 90), width=2)
    d2.text((80, 360), "Instructor Signature", fill=(80, 80, 80), font=font_small)

    d2.line([(400, 350), (620, 350)], fill=(150, 130, 90), width=2)
    d2.text((400, 360), "Lab In-Charge Signature", fill=(80, 80, 80), font=font_small)

    im2.save(out_jpg, format="JPEG", quality=90)


def generate_all() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating english.pdf...")
    build_english_pdf(FIXTURES_DIR / "english.pdf")
    print("Generating hindi.pdf...")
    build_hindi_pdf(FIXTURES_DIR / "hindi.pdf")
    print("Generating punjabi.pdf...")
    build_punjabi_pdf(FIXTURES_DIR / "punjabi.pdf")
    print("Generating scanned.pdf...")
    build_scanned_pdf(FIXTURES_DIR / "scanned.pdf")
    print("Generating image1.png and image2.jpg...")
    build_images(FIXTURES_DIR / "image1.png", FIXTURES_DIR / "image2.jpg")
    print("All fixtures generated successfully in:", FIXTURES_DIR)


if __name__ == "__main__":
    generate_all()
