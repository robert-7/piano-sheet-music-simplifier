import tempfile
import unittest
from pathlib import Path
from unittest import mock

from music21.lily.translate import LilyTranslateException

from src.piano_learning.commands import convert_musicxml_to_pdf
from src.piano_learning.utils import lilypond


class LilypondOutputPathTests(unittest.TestCase):
    """Regression tests for the LilyPond relative-path failure.

    LilyPond changes its working directory to the output directory, so a
    relative output path passed to music21 no longer resolves and rendering
    fails. The renderer must therefore hand music21 an absolute path.
    """

    def _make_src(self, tmp: str) -> Path:
        src = Path(tmp) / "Song.musicxml"
        src.write_text("<score/>", encoding="utf-8")
        return src

    def test_passes_absolute_path_to_music21(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self._make_src(tmp)
            score = mock.Mock()
            # music21 appends the format extension and returns the real path.
            score.write.side_effect = lambda fmt, fp: Path(f"{fp}.pdf")

            with mock.patch.object(lilypond, "_detect_lilypond", return_value="/usr/bin/lilypond"), \
                 mock.patch.object(lilypond, "environment"), \
                 mock.patch.object(lilypond.score_utils, "load_score", return_value=score):
                # Relative out_dir is exactly what run_e2e.sh passes.
                lilypond.convert_musicxml_to_pdf(str(src), out_dir=Path("user/output/run"), overwrite=True)

            fp = Path(score.write.call_args.kwargs["fp"])
            self.assertTrue(fp.is_absolute(), f"fp passed to music21 must be absolute, got {fp}")

    def test_returns_single_pdf_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self._make_src(tmp)
            score = mock.Mock()
            score.write.side_effect = lambda fmt, fp: Path(f"{fp}.pdf")

            with mock.patch.object(lilypond, "_detect_lilypond", return_value="/usr/bin/lilypond"), \
                 mock.patch.object(lilypond, "environment"), \
                 mock.patch.object(lilypond.score_utils, "load_score", return_value=score):
                result = lilypond.convert_musicxml_to_pdf(str(src), out_dir=Path(tmp), overwrite=True)

            self.assertTrue(str(result).endswith(".LilyPond.pdf"))
            self.assertFalse(str(result).endswith(".pdf.pdf"), "must not produce a double .pdf.pdf extension")
            self.assertTrue(Path(result).is_absolute())


class BackendFallbackTests(unittest.TestCase):
    """A LilyPond failure must not abort the MuseScore render."""

    def test_lilypond_failure_falls_back_to_musescore(self):
        muse_path = Path("/out/Song.MuseScore.pdf")
        with mock.patch.object(
            convert_musicxml_to_pdf.lilypond,
            "convert_musicxml_to_pdf",
            side_effect=LilyTranslateException("boom"),
        ), mock.patch.object(
            convert_musicxml_to_pdf.musescore,
            "convert_musicxml_to_pdf",
            return_value=muse_path,
        ):
            results = convert_musicxml_to_pdf.convert_musicxml_to_pdfs(
                "Song.musicxml",
                out_dir=Path("/out"),
                convert_with_lilypond=True,
                convert_with_musescore=True,
                overwrite=True,
            )

        self.assertEqual(results, {"MuseScore": muse_path})


if __name__ == "__main__":
    unittest.main()
