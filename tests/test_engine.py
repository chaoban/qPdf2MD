"""Engine tests: python -m unittest discover -s tests"""

import importlib.util
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qpdf2mk.engine import (  # noqa: E402
    Cancelled,
    ConvertOptions,
    PasswordRequired,
    convert_pdf,
    parse_page_range,
    resolve_output_path,
)
from qpdf2mk.tidy import count_words, tidy_markdown  # noqa: E402

HTML = """<h1>Quarterly Report 季度報告</h1>
<p>Plain paragraph with <b>bold</b> text. 這是繁體中文段落。</p>
<h2>Highlights</h2>
<ul><li>Revenue grew 12%</li><li>新產品上市</li></ul>
<table><tr><th>Region</th><th>Q1</th></tr><tr><td>North</td><td>120</td></tr></table>"""


def make_pdf(path: Path, pages: int = 2, password: str | None = None, image: bool = True) -> Path:
    import pymupdf

    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_htmlbox(page.rect + (50, 50, -50, -50), HTML, css="td,th{border:1px solid #000;padding:3px}")
        if image and i == pages - 1:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 80), 0)
            pix.set_rect(pix.irect, (40, 120, 200))
            page.insert_image(pymupdf.Rect(60, 520, 300, 680), pixmap=pix)
        page.insert_text((280, 810), str(i + 1), fontsize=9)
    kwargs = {}
    if password:
        kwargs = dict(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=password, owner_pw=password + "-owner")
    doc.save(path, **kwargs)
    return path


def make_scanned_pdf(path: Path, pages: int = 1) -> Path:
    """A PDF whose pages are only pictures of text, like the output of a scanner."""
    import pymupdf

    original = pymupdf.open(make_pdf(path.with_name(path.stem + "-original.pdf"), pages=pages, image=False))
    scan = pymupdf.open()
    for page in original:
        new = scan.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, pixmap=page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY))
    scan.save(path)
    return path


HAS_OCR = importlib.util.find_spec("rapidocr") is not None


class PageRangeTests(unittest.TestCase):
    def test_parses_lists_ranges_and_open_ends(self):
        self.assertEqual(parse_page_range("1-3, 5，8-", 10), [0, 1, 2, 4, 7, 8, 9])
        self.assertEqual(parse_page_range(" 2 - 4 ", 10), [1, 2, 3])
        self.assertEqual(parse_page_range("", 3), [0, 1, 2])
        self.assertEqual(parse_page_range("4-2", 5), [1, 2, 3])

    def test_rejects_bad_input(self):
        for bad in ("abc", "0-2", "20"):
            with self.assertRaises(ValueError):
                parse_page_range(bad, 10)

    def test_syntax_only_mode(self):
        self.assertEqual(parse_page_range("3", None), [2])
        with self.assertRaises(ValueError):
            parse_page_range("x-1", None)


class TidyTests(unittest.TestCase):
    def test_merges_split_code_blocks(self):
        md = "```\ndef f():\n```\n\n```\n    return 1\n```\n"
        self.assertEqual(tidy_markdown(md), "```\ndef f():\n    return 1\n```\n")

    def test_heading_bold_and_spacing(self):
        md = "text\n# **Title** here\nmore"
        self.assertEqual(tidy_markdown(md), "text\n\n# Title here\n\nmore\n")

    def test_reflows_paragraphs_cjk_aware(self):
        self.assertEqual(tidy_markdown("hello\nworld"), "hello world\n")
        self.assertEqual(tidy_markdown("中文第一行\n第二行"), "中文第一行第二行\n")
        self.assertEqual(tidy_markdown("conver-\nsion"), "conversion\n")

    def test_tight_lists_with_normalised_indent(self):
        md = "- a\n\n- b\n   - nested\n"
        self.assertEqual(tidy_markdown(md), "- a\n- b\n    - nested\n")

    def test_ocr_bullet_glyphs_become_list_items(self):
        self.assertEqual(tidy_markdown("- Revenue\n・新產品上市\n"), "- Revenue\n- 新產品上市\n")
        self.assertEqual(tidy_markdown("  - Revenue\n・新產品上市\n"), "- Revenue\n- 新產品上市\n")
        self.assertEqual(tidy_markdown("- Revenue grew 12% ・新產品上市"), "- Revenue grew 12%\n- 新產品上市\n")
        self.assertEqual(tidy_markdown("●first\n· second"), "- first\n- second\n")
        # separators that are not bullets stay as they are
        self.assertEqual(tidy_markdown("約翰・史密斯來訪"), "約翰・史密斯來訪\n")
        self.assertEqual(tidy_markdown("- Python · Java"), "- Python · Java\n")

    def test_word_count(self):
        self.assertEqual(count_words("# 標題\nhello world"), 4)


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fast_mode_with_image_folder(self):
        pdf = make_pdf(self.dir / "report 報告.pdf", pages=2)
        result = convert_pdf(pdf, ConvertOptions(mode="fast", images="folder"))
        self.assertTrue(result.output_path.exists())
        md = result.output_path.read_text(encoding="utf-8")
        self.assertIn("# Quarterly Report", md)
        self.assertIn("|Region|Q1|", md.replace(" ", ""))
        self.assertEqual(result.images, 1)
        self.assertIn("](<report 報告_images/p002-01.png>)", md)
        self.assertTrue((self.dir / "report 報告_images" / "p002-01.png").exists())
        self.assertNotRegex(md, r"(?m)^\s*2\s*$")  # page number stripped

    def test_rename_on_conflict_and_page_range(self):
        pdf = make_pdf(self.dir / "a.pdf", pages=3, image=False)
        first = convert_pdf(pdf, ConvertOptions(mode="fast", images="none"))
        second = convert_pdf(pdf, ConvertOptions(mode="fast", images="none", page_range="2"))
        self.assertEqual(first.output_path.name, "a.md")
        self.assertEqual(second.output_path.name, "a (1).md")
        self.assertEqual(second.pages, 1)
        self.assertEqual(resolve_output_path(pdf, ConvertOptions(overwrite=True)).name, "a.md")

    def test_front_matter_and_markers(self):
        pdf = make_pdf(self.dir / "b.pdf", pages=2, image=False)
        result = convert_pdf(pdf, ConvertOptions(mode="fast", images="none", front_matter=True, page_markers=True))
        self.assertTrue(result.markdown.startswith("---\ntitle: "))
        self.assertIn("<!-- page 2 -->", result.markdown)

    def test_password(self):
        pdf = make_pdf(self.dir / "locked.pdf", pages=1, password="1234", image=False)
        with self.assertRaises(PasswordRequired):
            convert_pdf(pdf, ConvertOptions(mode="fast"))
        with self.assertRaises(PasswordRequired):
            convert_pdf(pdf, ConvertOptions(mode="fast"), password="nope")
        result = convert_pdf(pdf, ConvertOptions(mode="fast", images="none"), password="1234")
        self.assertIn("Quarterly Report", result.markdown)

    def test_cancel(self):
        pdf = make_pdf(self.dir / "c.pdf", pages=6, image=False)
        stop = threading.Event()
        stop.set()
        with self.assertRaises(Cancelled):
            convert_pdf(pdf, ConvertOptions(mode="fast"), cancel_event=stop)
        self.assertFalse((self.dir / "c.md").exists())

    def test_layout_mode(self):
        pdf = make_pdf(self.dir / "d.pdf", pages=1)
        progress = []
        result = convert_pdf(pdf, ConvertOptions(mode="layout", images="embed"), progress=lambda f, t: progress.append(f))
        self.assertIn("## Highlights", result.markdown)
        self.assertIn("- Revenue grew 12%", result.markdown)
        self.assertEqual(progress[-1], 1.0)


@unittest.skipUnless(HAS_OCR, "RapidOCR is not installed")
class OcrTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.scan = make_scanned_pdf(self.dir / "scan.pdf")

    def tearDown(self):
        self.tmp.cleanup()

    def test_layout_mode_reads_scanned_page(self):
        result = convert_pdf(self.scan, ConvertOptions(mode="layout", ocr="auto", images="folder"))
        self.assertEqual(result.ocr_pages, 1)
        self.assertIn("Quarterly Report", result.markdown)
        self.assertIn("繁體中文", result.markdown)
        self.assertIn("## Highlights", result.markdown)

    def test_fast_mode_reads_scan_without_copying_it_as_an_image(self):
        result = convert_pdf(self.scan, ConvertOptions(mode="fast", ocr="auto", images="folder"))
        self.assertEqual(result.ocr_pages, 1)
        self.assertIn("# Quarterly Report", result.markdown)
        self.assertIn("新產品上市", result.markdown)
        self.assertEqual(result.images, 0)
        self.assertFalse((self.dir / "scan_images").exists())

    def test_ocr_off_leaves_scan_unread(self):
        result = convert_pdf(self.scan, ConvertOptions(mode="layout", ocr="off", images="none"))
        self.assertEqual(result.ocr_pages, 0)
        self.assertNotIn("Quarterly", result.markdown)

    def test_auto_skips_pages_that_have_text(self):
        pdf = make_pdf(self.dir / "digital.pdf", pages=2)
        for mode in ("layout", "fast"):
            result = convert_pdf(pdf, ConvertOptions(mode=mode, ocr="auto", images="none", overwrite=True))
            self.assertEqual(result.ocr_pages, 0, mode)

    def test_cancel_during_ocr(self):
        stop = threading.Event()

        def progress(fraction, text):
            if "OCR" in text and "辨識" in text:
                stop.set()

        with self.assertRaises(Cancelled):
            convert_pdf(make_scanned_pdf(self.dir / "scan3.pdf", pages=3), ConvertOptions(mode="fast", ocr="always"),
                        progress=progress, cancel_event=stop)


if __name__ == "__main__":
    unittest.main()
