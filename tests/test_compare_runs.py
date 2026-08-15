import json
import tempfile
import unittest
from pathlib import Path

from src.piano_learning.commands import compare_runs
from src.piano_learning.utils import simplification_report


def _report(pct_changed, textures):
    per_measure = [
        {
            "number": number,
            "changed": texture != "preserve",
            "planTexture": texture,
            "sourceNoteCount": 4,
            "planNoteCount": 4,
        }
        for number, texture in enumerate(textures, start=1)
    ]
    report = simplification_report.summarize_measures(per_measure)
    # summarize_measures derives pctChanged from the measures; assert the
    # fixture matches what the caller expects so tests stay honest.
    assert report["pctChanged"] == pct_changed, report["pctChanged"]
    return report


class CompareRunsTests(unittest.TestCase):
    def test_happy_path_writes_and_returns_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_a_dir = tmp_path / "run-a"
            run_b_dir = tmp_path / "run-b"
            out_dir = tmp_path / "out"
            run_a_dir.mkdir()
            run_b_dir.mkdir()

            report_a = _report(50.0, ["block", "preserve"])
            report_b = _report(0.0, ["preserve", "preserve"])
            simplification_report.write_report(report_a, run_a_dir, "song")
            simplification_report.write_report(report_b, run_b_dir, "song")

            diff = compare_runs.compare_runs(run_a_dir, run_b_dir, out_dir)

            self.assertEqual(diff["pctChanged"]["a"], 50.0)
            self.assertEqual(diff["pctChanged"]["b"], 0.0)
            self.assertEqual(len(diff["divergentMeasures"]), 1)

            written_path = out_dir / "runs_comparison.json"
            self.assertTrue(written_path.exists())
            self.assertEqual(json.loads(written_path.read_text(encoding="utf-8")), diff)

    def test_missing_report_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            missing_dir = tmp_path / "missing"
            missing_dir.mkdir()

            with self.assertRaises(FileNotFoundError):
                compare_runs.compare_runs(missing_dir, missing_dir, tmp_path / "out")


if __name__ == "__main__":
    unittest.main()
