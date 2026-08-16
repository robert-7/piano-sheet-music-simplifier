import tempfile
import unittest
from pathlib import Path

from music21 import bar

from src.piano_learning.utils import musicxml_rewriter
from src.piano_learning.utils import score_utils
from src.piano_learning.utils import simplification_plan
from tests import fixtures


def _repeat_score_plan() -> dict:
    return {
        "schemaVersion": simplification_plan.PLAN_SCHEMA_VERSION,
        "scope": simplification_plan.PLAN_SCOPE,
        "measures": [
            {
                "number": 1,
                "texture": "block",
                "events": [{"offset": 0.0, "duration": 4.0, "pitches": ["C2", "G2"]}],
            },
            {"number": 2, "texture": "preserve", "events": []},
        ],
    }


class RepeatBarlinePreservationTests(unittest.TestCase):
    def test_repeat_barlines_survive_lh_only_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "repeats.musicxml"
            fixtures.score_with_repeat_barlines().write("musicxml", fp=str(input_path))
            output_path = tmp_path / "simplified.musicxml"

            musicxml_rewriter.write_simplified_musicxml_from_plan(
                str(input_path), _repeat_score_plan(), str(output_path)
            )

            output_score = score_utils.load_score(str(output_path))
            rh_measures = {
                int(m.number): m for m in output_score.parts[0].getElementsByClass("Measure")
            }
            lh_measures = {
                int(m.number): m for m in output_score.parts[-1].getElementsByClass("Measure")
            }

            for measures in (rh_measures, lh_measures):
                self.assertIsInstance(measures[1].leftBarline, bar.Repeat)
                self.assertEqual(measures[1].leftBarline.direction, "start")
                self.assertIsInstance(measures[2].rightBarline, bar.Repeat)
                self.assertEqual(measures[2].rightBarline.direction, "end")


if __name__ == "__main__":
    unittest.main()
