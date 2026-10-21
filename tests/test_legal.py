"""Tests for the license viewer data and the MSIX packaging helpers (no Qt window needed)."""

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packaging"))

from qpdf2mk import legal  # noqa: E402


class LegalTests(unittest.TestCase):
    def test_license_texts_present(self):
        for title, name in legal.LICENSE_TABS:
            text = legal.license_text(name)
            self.assertIn("GENERAL PUBLIC LICENSE", text, title)
        self.assertEqual((ROOT / "LICENSE").read_text(encoding="utf-8"), legal.license_text("AGPL-3.0.txt"))

    def test_notices_cover_runtime_packages(self):
        text = legal.build_third_party_notices()
        self.assertIn("Third-Party Software Notices", text)
        self.assertIn("LGPL-3.0", text)
        self.assertIn("Artifex", text)
        for dist in legal.runtime_distributions():
            self.assertIn(f". {dist.metadata['Name']}\n", text)

    def test_runtime_closure_includes_dependencies(self):
        names = {legal._norm(d.metadata["Name"]) for d in legal.runtime_distributions()}
        self.assertTrue({"pymupdf", "pymupdf4llm", "rapidocr", "numpy"} <= names)
        self.assertNotIn("pyinstaller", names)


class MsixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import make_msix
        cls.m = make_msix

    def test_version(self):
        self.assertEqual(self.m.msix_version("1.0.0"), "1.0.0.0")
        self.assertEqual(self.m.msix_version("2.1"), "2.1.0.0")
        for bad in ("1.0.0.3", "1.x", ""):
            with self.assertRaises(self.m.BuildError):
                self.m.msix_version(bad)

    def test_manifest_is_valid_xml(self):
        ident = {"Name": "12345SAISAI.qPdf2MD", "Publisher": "CN=1A2B3C4D-1111-2222-3333-444455556666",
                 "PublisherDisplayName": "SAISAI & Co"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AppxManifest.xml"
            self.m.write_manifest(path, ident, "1.0.0.0")
            root = ET.parse(path).getroot()
        ns = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
        identity = root.find("m:Identity", ns)
        self.assertEqual(identity.get("Name"), ident["Name"])
        self.assertEqual(identity.get("Version"), "1.0.0.0")
        self.assertEqual(root.find("m:Properties/m:PublisherDisplayName", ns).text, "SAISAI & Co")
        app = root.find("m:Applications/m:Application", ns)
        self.assertEqual(app.get("Executable"), "qPdf2MD.exe")
        self.assertEqual(app.get("EntryPoint"), "Windows.FullTrustApplication")

    def test_placeholder_identity_rejected(self):
        saved = self.m.IDENTITY_FILE
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store_identity.json"
            path.write_text('{"Name": "XXXXX.qPdf2MD", "Publisher": "CN=XXXXXXXX", "PublisherDisplayName": "SAISAI"}',
                            encoding="utf-8")
            self.m.IDENTITY_FILE = path
            try:
                with self.assertRaises(self.m.BuildError):
                    self.m.load_identity()
            finally:
                self.m.IDENTITY_FILE = saved

    def test_committed_identity_is_valid(self):
        ident = self.m.load_identity()
        self.assertTrue(ident["Publisher"].startswith("CN="))


if __name__ == "__main__":
    unittest.main()
