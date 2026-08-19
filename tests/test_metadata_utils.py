import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from music21 import converter

from src.piano_learning.utils import metadata_utils

# A minimal Audiveris-style score with no title/composer, mirroring what an
# image-only PDF produces when OCR captures no text.
MINIMAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0.3 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0.3">
  <identification>
    <encoding>
      <software>Audiveris 5.11.0</software>
    </encoding>
  </identification>
  <part-list>
    <score-part id="P1"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <note><rest measure="yes"/><duration>4</duration></note>
    </measure>
  </part>
</score-partwise>
"""


def _write(tmp: Path, name: str, content: str) -> Path:
    path = tmp / name
    path.write_text(content, encoding="utf-8")
    return path


class CleanTitleTests(unittest.TestCase):
    def test_strips_notation_suffix_and_whitespace(self):
        self.assertEqual(metadata_utils.clean_title("  Kakariko Village.musx "), "Kakariko Village")
        self.assertEqual(metadata_utils.clean_title("Song.MSCZ"), "Song")

    def test_returns_none_for_empty_or_suffix_only(self):
        self.assertIsNone(metadata_utils.clean_title(None))
        self.assertIsNone(metadata_utils.clean_title("   "))
        self.assertIsNone(metadata_utils.clean_title(".musx"))

    def test_keeps_plain_title(self):
        self.assertEqual(metadata_utils.clean_title("Clair de Lune"), "Clair de Lune")


class ReadPdfMetadataTests(unittest.TestCase):
    def _make_pdf(self, tmp: Path, metadata: dict | None) -> Path:
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        if metadata is not None:
            writer.add_metadata(metadata)
        path = tmp / "score.pdf"
        with open(path, "wb") as handle:
            writer.write(handle)
        return path

    def test_reads_and_cleans_title_and_author(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = self._make_pdf(Path(tmp), {"/Title": "Kakariko Village.musx", "/Author": "Matt386"})
            self.assertEqual(metadata_utils.read_pdf_metadata(pdf), ("Kakariko Village", "Matt386"))

    def test_missing_metadata_yields_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = self._make_pdf(Path(tmp), {})
            self.assertEqual(metadata_utils.read_pdf_metadata(pdf), (None, None))

    def test_unreadable_pdf_never_raises(self):
        with self.assertLogs(metadata_utils.logger, level="WARNING"):
            self.assertEqual(metadata_utils.read_pdf_metadata("/no/such/file.pdf"), (None, None))


class BackfillMusicxmlMetadataTests(unittest.TestCase):
    def test_inserts_missing_title_and_composer(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = _write(Path(tmp), "s.xml", MINIMAL_XML)
            changed = metadata_utils.backfill_musicxml_metadata(xml_path, title="My Title", composer="A Composer")
            self.assertTrue(changed)

            root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
            self.assertEqual(root.find("work/work-title").text, "My Title")
            creators = root.findall("identification/creator")
            self.assertEqual([(c.get("type"), c.text) for c in creators], [("composer", "A Composer")])
            # <work> must precede <identification> for valid MusicXML ordering.
            self.assertEqual(list(root)[0].tag, "work")

    def test_preserves_doctype(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = _write(Path(tmp), "s.xml", MINIMAL_XML)
            metadata_utils.backfill_musicxml_metadata(xml_path, title="T", composer="C")
            self.assertIn("<!DOCTYPE score-partwise", xml_path.read_text(encoding="utf-8"))

    def test_does_not_override_existing_metadata(self):
        existing = MINIMAL_XML.replace(
            "  <identification>",
            "  <work><work-title>Real Title</work-title></work>\n  <identification>\n    <creator type=\"composer\">Real Composer</creator>",
        )
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = _write(Path(tmp), "s.xml", existing)
            changed = metadata_utils.backfill_musicxml_metadata(xml_path, title="Wrong", composer="Wrong")
            self.assertFalse(changed)

            root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
            self.assertEqual(root.find("work/work-title").text, "Real Title")
            self.assertEqual(root.find("identification/creator").text, "Real Composer")

    def test_respects_existing_movement_title(self):
        """Audiveris stores an OCR'd title in <movement-title>; the PDF fallback must defer to it."""
        with_movement = MINIMAL_XML.replace(
            "  <identification>",
            "  <movement-title>OCR Title</movement-title>\n  <identification>",
        )
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = _write(Path(tmp), "s.xml", with_movement)
            changed = metadata_utils.backfill_musicxml_metadata(xml_path, title="PDF Title", composer=None)
            self.assertFalse(changed)
            self.assertIsNone(ET.fromstring(xml_path.read_text(encoding="utf-8")).find("work"))

    def test_creates_identification_when_absent(self):
        no_ident = MINIMAL_XML.replace(
            "  <identification>\n    <encoding>\n      <software>Audiveris 5.11.0</software>\n    </encoding>\n  </identification>\n",
            "",
        )
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = _write(Path(tmp), "s.xml", no_ident)
            self.assertTrue(metadata_utils.backfill_musicxml_metadata(xml_path, composer="C"))
            root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
            self.assertEqual(root.find("identification/creator").text, "C")

    def test_noop_when_nothing_to_add(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = _write(Path(tmp), "s.xml", MINIMAL_XML)
            self.assertFalse(metadata_utils.backfill_musicxml_metadata(xml_path, title=None, composer=None))


class NormalizeOutputMetadataTests(unittest.TestCase):
    def _write_and_read_tags(self, score) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.musicxml"
            score.write("musicxml", fp=str(out))
            return out.read_text(encoding="utf-8")

    def test_strips_filename_title_and_music21_composer(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = _write(Path(tmp), "Kakariko_Village.xml", MINIMAL_XML)
            score = converter.parse(str(xml_path))

            metadata_utils.normalize_output_metadata(score)
            xml = self._write_and_read_tags(score)

            self.assertNotIn("Music21", xml)
            self.assertNotIn("Kakariko_Village.xml", xml)

    def test_preserves_ocr_movement_title(self):
        """A real <movement-title> (from OCR) must survive normalization, not be blanked."""
        with_movement = MINIMAL_XML.replace(
            "  <identification>",
            "  <movement-title>Kakariko Village</movement-title>\n  <identification>",
        )
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = _write(Path(tmp), "Kakariko_Village.xml", with_movement)
            score = converter.parse(str(xml_path))

            metadata_utils.normalize_output_metadata(score, source_name=xml_path)
            xml = self._write_and_read_tags(score)

            self.assertIn("<movement-title>Kakariko Village</movement-title>", xml)
            self.assertNotIn("Music21", xml)

    def test_mirrors_real_title_into_movement_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = _write(Path(tmp), "s.xml", MINIMAL_XML)
            metadata_utils.backfill_musicxml_metadata(xml_path, title="Kakariko Village", composer="Matt386")
            score = converter.parse(str(xml_path))

            metadata_utils.normalize_output_metadata(score)
            xml = self._write_and_read_tags(score)

            self.assertIn("<work-title>Kakariko Village</work-title>", xml)
            self.assertIn("<movement-title>Kakariko Village</movement-title>", xml)
            self.assertIn('<creator type="composer">Matt386</creator>', xml)
            self.assertNotIn("Music21", xml)


if __name__ == "__main__":
    unittest.main()
