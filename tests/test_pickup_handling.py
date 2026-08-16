import tempfile
import unittest
from pathlib import Path

from src.piano_learning.utils import musicxml_rewriter
from src.piano_learning.utils import score_utils
from src.piano_learning.utils import simplification_plan
from tests import fixtures


def _pickup_plan() -> dict:
    return {
        "schemaVersion": simplification_plan.PLAN_SCHEMA_VERSION,
        "scope": simplification_plan.PLAN_SCOPE,
        "measures": [
            {
                "number": 0,
                "texture": "singleBass",
                "events": [{"offset": 0.0, "duration": 1.0, "pitches": ["C2"]}],
            },
            {
                "number": 1,
                "texture": "block",
                "events": [{"offset": 0.0, "duration": 4.0, "pitches": ["D2", "D3"]}],
            },
        ],
    }


class PickupMeasureHandlingTests(unittest.TestCase):
    def test_measure_grid_reports_actual_pickup_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "pickup.musicxml"
            fixtures.pickup_measure_score().write("musicxml", fp=str(input_path))

            grid = musicxml_rewriter.get_measure_grid(str(input_path))

        durations_by_number = {entry["number"]: entry["duration"] for entry in grid}
        # Measure 0 is a one-beat pickup in a 4/4 score; its duration must reflect
        # the notated 1.0 ql, not the full 4.0 ql bar length implied by the time
        # signature, or plan validation will demand LH content that can't exist.
        self.assertEqual(durations_by_number[0], 1.0)
        self.assertEqual(durations_by_number[1], 4.0)

    def test_plan_applies_correctly_to_pickup_measure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "pickup.musicxml"
            fixtures.pickup_measure_score().write("musicxml", fp=str(input_path))
            output_path = tmp_path / "simplified.musicxml"

            musicxml_rewriter.write_simplified_musicxml_from_plan(
                str(input_path), _pickup_plan(), str(output_path)
            )

            output_score = score_utils.load_score(str(output_path))
            lh_measures = {
                int(measure.number): measure
                for measure in output_score.parts[-1].getElementsByClass("Measure")
            }
            self.assertEqual(lh_measures[0].highestTime, 1.0)
            self.assertEqual(lh_measures[1].highestTime, 4.0)


if __name__ == "__main__":
    unittest.main()
