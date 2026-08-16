import tempfile
import unittest
from pathlib import Path

from src.piano_learning.utils import musicxml_rewriter
from src.piano_learning.utils import score_utils
from src.piano_learning.utils import simplification_plan
from tests import fixtures


def _full_coverage_plan() -> dict:
    return {
        "schemaVersion": simplification_plan.PLAN_SCHEMA_VERSION,
        "scope": simplification_plan.PLAN_SCOPE,
        "measures": [
            {
                "number": 1,
                "texture": "block",
                "events": [{"offset": 0.0, "duration": 4.0, "pitches": ["C2", "G2"]}],
            },
            {
                "number": 2,
                "texture": "block",
                "events": [{"offset": 0.0, "duration": 4.0, "pitches": ["C2", "G2"]}],
            },
        ],
    }


class MusicXmlRoundTripTests(unittest.TestCase):
    def test_rewritten_musicxml_reparses_and_preserves_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.musicxml"
            fixtures.two_measure_broken_arpeggio_score().write("musicxml", fp=str(input_path))
            output_path = tmp_path / "simplified.musicxml"

            musicxml_rewriter.write_simplified_musicxml_from_plan(
                str(input_path), _full_coverage_plan(), str(output_path)
            )

            # A parseable output that music21 accepts back as a Score is the
            # regression this guards: a previous observed failure mode was
            # writing output that "succeeded" but wasn't valid MusicXML.
            output_score = score_utils.load_score(str(output_path))

            self.assertEqual(len(output_score.parts), 2)
            for part in output_score.parts:
                measure_numbers = [
                    int(m.number) for m in part.getElementsByClass("Measure")
                ]
                self.assertEqual(measure_numbers, [1, 2])


if __name__ == "__main__":
    unittest.main()
