"""Translation tests: python -m unittest discover -s tests

Every Traditional Chinese string in the program must be a message key with an English entry, and each entry
must use the same placeholders as its key. The check reads the source, so a new hard-coded string fails here.
"""

import ast
import re
import string
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qpdf2mk import i18n  # noqa: E402
from qpdf2mk.i18n.en import MESSAGES as EN  # noqa: E402

PACKAGE = ROOT / "qpdf2mk"
CJK = re.compile(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]")
# Not UI text: the license notices are bilingual by design, tidy.py and the regexes match document content.
EXEMPT_FILES = {"legal.py", "tidy.py"}
REGEX_HINT = re.compile(r"\\[sd]|\[|\(\?")


def _source_strings() -> list[tuple[str, int, str, bool]]:
    """(file, line, text, inside_fstring) for every non-docstring string literal that contains CJK text."""
    found = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if "i18n" in path.parts or path.name in EXEMPT_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docstrings.add(id(first.value))
        in_fstring = {id(v) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for v in node.values}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
                    and CJK.search(node.value) and not REGEX_HINT.search(node.value)):
                found.append((path.name, node.lineno, node.value, id(node) in in_fstring))
    return found


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


class CatalogTests(unittest.TestCase):
    def test_every_ui_string_has_english(self):
        keys = {k.split("|", 1)[-1] for k in EN}
        missing = [f"{f}:{line} {text!r}" for f, line, text, _ in _source_strings() if text not in keys]
        self.assertEqual(missing, [], "add these to qpdf2mk/i18n/en.py")

    def test_no_chinese_inside_fstrings(self):
        bad = [f"{f}:{line} {text!r}" for f, line, text, fs in _source_strings() if fs]
        self.assertEqual(bad, [], "use tr() with named placeholders instead of an f-string")

    def test_no_unused_entries(self):
        used = set()
        for path in PACKAGE.rglob("*.py"):
            if path.name != "en.py":
                tree = ast.parse(path.read_text(encoding="utf-8"))
                used |= {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        unused = [k for k in EN if k.split("|", 1)[-1] not in used]
        self.assertEqual(unused, [], "remove stale entries from qpdf2mk/i18n/en.py")

    def test_placeholders_match(self):
        for key, value in EN.items():
            source = key.split("|", 1)[-1]
            forms = value if isinstance(value, tuple) else (value,)
            self.assertIn(len(forms), (1, 2), key)
            for form in forms:
                self.assertEqual(_fields(form), _fields(source), f"{key!r} -> {form!r}")
                form.format(**{name: 1 for name in _fields(form)})  # format specs such as {n:,} must work


class TrTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language(i18n.SOURCE)

    def test_source_language_returns_key(self):
        i18n.set_language("zh_TW")
        self.assertEqual(i18n.tr("已加入 {n} 個檔案", n=3), "已加入 3 個檔案")
        self.assertEqual(i18n.tr("關閉", context="ocr"), "關閉")

    def test_english_plural_and_context(self):
        self.assertEqual(i18n.set_language("en"), "en")
        self.assertEqual(i18n.tr("已加入 {n} 個檔案", n=1), "Added 1 file")
        self.assertEqual(i18n.tr("已加入 {n} 個檔案", n=2), "Added 2 files")
        self.assertEqual(i18n.tr("{n:,} 字", n=12345), "12,345 words")
        self.assertEqual(i18n.tr("關閉"), "Close")
        self.assertEqual(i18n.tr("關閉", context="ocr"), "Off")
        self.assertEqual(i18n.tr("跟隨系統", context="no-such-context"), "System")

    def test_unknown_text_falls_back(self):
        i18n.set_language("en")
        self.assertEqual(i18n.tr("沒有這個字串 {x}", x=1), "沒有這個字串 1")
        self.assertEqual(i18n.set_language("xx"), i18n.SOURCE)

    def test_system_language_matching(self):
        self.assertEqual(i18n.match_language(["zh-Hant-TW", "en-US"]), "zh_TW")
        self.assertEqual(i18n.match_language(["zh-CN"]), "zh_TW")
        self.assertEqual(i18n.match_language(["en-GB", "zh-TW"]), "en")
        self.assertEqual(i18n.match_language(["ja-JP", "zh-TW"]), "zh_TW")
        self.assertEqual(i18n.match_language(["de-DE"]), "en")
        self.assertEqual(i18n.resolve("en"), "en")
        self.assertEqual(i18n.resolve("zh_TW"), "zh_TW")
        self.assertIn(i18n.resolve("system"), i18n.LANGUAGES)

    def test_engine_messages_follow_language(self):
        from qpdf2mk.engine import parse_page_range

        i18n.set_language("en")
        with self.assertRaisesRegex(ValueError, "Page numbers start at 1"):
            parse_page_range("0-2", 5)
        self.assertEqual(parse_page_range("2 to 4", 5), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
