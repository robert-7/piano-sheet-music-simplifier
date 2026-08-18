import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.piano_learning.utils import audiveris


class ConvertPdfToMusicxmlRasterizeTests(unittest.TestCase):
    """Covers the rasterize-vs-direct-PDF input selection (issue #97).

    Passing per-page images to Audiveris makes it emit one book per page
    (e.g. page-001.xml, page-002.xml) instead of one merged score, so
    rasterizing must be opt-in rather than the default.
    """

    def _touch_pdf(self, tmp: str) -> Path:
        pdf_path = Path(tmp) / "Song.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        return pdf_path

    def test_default_passes_pdf_directly_to_audiveris(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = self._touch_pdf(tmp)
            out_dir = Path(tmp) / "out"

            with (
                mock.patch.object(audiveris, "check_java"),
                mock.patch.object(audiveris.image_utils, "pdf_to_images") as mock_rasterize,
                mock.patch.object(audiveris, "run_audiveris") as mock_run,
            ):
                mock_run.return_value = audiveris.ConversionResult(
                    outputs=[out_dir / "Song.xml"], log_path=out_dir / "audiveris.log", workspace=out_dir
                )

                audiveris.convert_pdf_to_musicxml(pdf_path, out_dir)

            mock_rasterize.assert_not_called()
            mock_run.assert_called_once_with([pdf_path], out_dir=out_dir)

    def test_explicit_rasterize_true_uses_page_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = self._touch_pdf(tmp)
            out_dir = Path(tmp) / "out"
            img_paths = [Path(tmp) / "images" / "page-001.png"]

            with (
                mock.patch.object(audiveris, "check_java"),
                mock.patch.object(audiveris.image_utils, "pdf_to_images", return_value=img_paths) as mock_rasterize,
                mock.patch.object(audiveris.image_utils, "preprocess_images_inplace") as mock_preprocess,
                mock.patch.object(audiveris, "run_audiveris") as mock_run,
            ):
                mock_run.return_value = audiveris.ConversionResult(
                    outputs=[out_dir / "page-001.xml"], log_path=out_dir / "audiveris.log", workspace=out_dir
                )

                audiveris.convert_pdf_to_musicxml(pdf_path, out_dir, prefer_rasterize=True)

            mock_rasterize.assert_called_once()
            mock_preprocess.assert_called_once_with(img_paths)
            mock_run.assert_called_once_with(img_paths, out_dir=out_dir)


if __name__ == "__main__":
    unittest.main()
