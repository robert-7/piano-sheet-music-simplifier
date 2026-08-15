import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.piano_learning.commands import generate_simplified_musicxml_using_ai as gen_ai


class GenerateSimplifiedAiErrorHandlingTests(unittest.TestCase):
    def test_failure_propagates_instead_of_returning_none(self):
        # Regression for #80: generate_simplified_musicxml used to wrap its whole
        # body in `except Exception: return None`, so any failure was swallowed
        # into a silent None (indistinguishable from an unmodified plan). A
        # missing output directory must now raise, not return None.
        missing_out_dir = Path("/nonexistent-piano-sheet-music-out-dir/does-not-exist")
        self.assertFalse(missing_out_dir.exists())

        with self.assertRaises(FileNotFoundError):
            gen_ai.generate_simplified_musicxml(
                "user/input/example.musicxml",
                missing_out_dir,
            )


class GenerateSimplifiedAiObservabilityTests(unittest.TestCase):
    """
    Issue #72: a run that fails validation must still leave the raw model output
    and a validation report behind. Previously those were written only after a
    successful validate_plan, so a bad response vanished. We mock the two real
    boundaries (music21 analysis and the OpenAI call) so this stays a fast,
    key-free unit test.
    """

    def test_validation_failure_still_persists_output_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            with (
                mock.patch.object(gen_ai.generate_analysis_of_musicxml, "build_analysis_bundle", return_value={}),
                mock.patch.object(gen_ai.musicxml_rewriter, "get_measure_grid", return_value=[{"number": 1}]),
                mock.patch.object(gen_ai.simplification_plan, "compact_analysis_for_plan", return_value={}),
                mock.patch.object(
                    gen_ai.openai_utils,
                    "run_openai_response_in_background",
                    return_value=("this is not json", "some reasoning"),
                ),
            ):
                with self.assertRaises(ValueError):
                    gen_ai.generate_simplified_musicxml("Song.musicxml", out_dir)

            # Raw output + reasoning were written despite the validation failure.
            self.assertEqual(
                (out_dir / "Song_model_output_raw.txt").read_text(encoding="utf-8"),
                "this is not json",
            )
            self.assertEqual(
                (out_dir / "Song_model_reasoning.txt").read_text(encoding="utf-8"),
                "some reasoning",
            )

            # A validation report explains the failure.
            validation = json.loads((out_dir / "Song_validation_report.json").read_text(encoding="utf-8"))
            self.assertEqual(validation["status"], "failed")
            self.assertIn("ValueError", validation["error"])

            # No plan or simplified score was produced.
            self.assertFalse((out_dir / "Song_simplification_plan.json").exists())
            self.assertFalse((out_dir / "Song_simplified.musicxml").exists())

            # The run summary indexes the failure and its request characteristics.
            summary = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["outcome"], "failed")
            self.assertEqual(summary["mode"], "responses_background")
            self.assertEqual(summary["validation"]["status"], "failed")
            by_role = {entry["role"]: entry for entry in summary["artifacts"]}
            self.assertTrue(by_role["model_output_raw"]["exists"])
            self.assertFalse(by_role["plan"]["exists"])


if __name__ == "__main__":
    unittest.main()
