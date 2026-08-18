import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.piano_learning.commands import convert_pdf_to_musicxml
from src.piano_learning.utils.audiveris import ConversionResult


class ConvertPdfToMusicxmlTests(unittest.TestCase):
    """Command-level tests for the Audiveris-backed PDF -> MusicXML step.

    Audiveris itself (a Java process) is out of scope here; these tests only
    verify the command wrapper's contract with ``audiveris.convert_pdf_to_musicxml``.
    """

    def test_returns_single_output_on_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            outputs = [out_dir / "Song.xml"]
            result = ConversionResult(outputs=outputs, log_path=out_dir / "audiveris.log", workspace=out_dir)

            with mock.patch.object(
                convert_pdf_to_musicxml.audiveris,
                "convert_pdf_to_musicxml",
                return_value=result,
            ) as mocked:
                returned = convert_pdf_to_musicxml.convert_pdf_to_musicxml(
                    pdf_path=Path("Song.pdf"),
                    out_dir=out_dir,
                    prefer_rasterize=False,
                    dpi=400,
                )

            self.assertEqual(returned, outputs[0])
            mocked.assert_called_once_with(
                pdf_path=Path("Song.pdf"),
                out_dir=out_dir,
                prefer_rasterize=False,
                dpi=400,
            )

    def test_raises_on_multiple_outputs(self):
        """A multi-page/multi-book Audiveris result must not silently use only the first page."""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            outputs = [out_dir / "page-001.xml", out_dir / "page-002.xml"]
            result = ConversionResult(outputs=outputs, log_path=out_dir / "audiveris.log", workspace=out_dir)

            with mock.patch.object(
                convert_pdf_to_musicxml.audiveris,
                "convert_pdf_to_musicxml",
                return_value=result,
            ):
                with self.assertRaisesRegex(RuntimeError, "page-001.xml"):
                    convert_pdf_to_musicxml.convert_pdf_to_musicxml(
                        pdf_path=Path("Song.pdf"),
                        out_dir=out_dir,
                        prefer_rasterize=False,
                        dpi=400,
                    )

    def test_propagates_audiveris_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)

            with mock.patch.object(
                convert_pdf_to_musicxml.audiveris,
                "convert_pdf_to_musicxml",
                side_effect=RuntimeError("Audiveris failed (code 1)."),
            ):
                with self.assertRaisesRegex(RuntimeError, "Audiveris failed"):
                    convert_pdf_to_musicxml.convert_pdf_to_musicxml(
                        pdf_path=Path("Song.pdf"),
                        out_dir=out_dir,
                        prefer_rasterize=True,
                        dpi=400,
                    )


if __name__ == "__main__":
    unittest.main()
