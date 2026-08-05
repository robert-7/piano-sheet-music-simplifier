import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
