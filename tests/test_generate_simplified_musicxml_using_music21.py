import tempfile
import unittest
from pathlib import Path

from src.piano_learning.commands import generate_simplified_musicxml_using_music21 as music21_cmd
from src.piano_learning.utils import score_utils
from tests import fixtures


class GenerateSimplifiedMusicxmlUsingMusic21Tests(unittest.TestCase):
    def test_happy_path_writes_musicxml_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.musicxml"
            fixtures.two_measure_broken_arpeggio_score().write("musicxml", fp=str(input_path))
            out_dir = tmp_path / "out"

            result_path = music21_cmd.generate_simplified_musicxml_using_music21(
                str(input_path), out_dir=str(out_dir)
            )

            self.assertIsNotNone(result_path)
            self.assertTrue(Path(result_path).exists())

            reports = list(out_dir.glob("*_simplification_report.json"))
            self.assertEqual(len(reports), 1)

            summaries = list(out_dir.glob("run_summary.json"))
            self.assertEqual(len(summaries), 1)

            # RH must be untouched; only the LH is simplified.
            output_score = score_utils.load_score(result_path)
            rh_notes = list(output_score.parts[0].flatten().notes)
            self.assertEqual(len(rh_notes), 2)
            self.assertEqual([n.pitch.nameWithOctave for n in rh_notes], ["C5", "C5"])

    def test_reduces_left_hand_to_fewer_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.musicxml"
            fixtures.two_measure_broken_arpeggio_score().write("musicxml", fp=str(input_path))
            out_dir = tmp_path / "out"

            result_path = music21_cmd.generate_simplified_musicxml_using_music21(
                str(input_path), out_dir=str(out_dir)
            )

            output_score = score_utils.load_score(result_path)
            lh_events = list(output_score.parts[-1].flatten().notesAndRests)
            # Source LH had 16 sixteenth-note events per measure (32 total);
            # the beat-window reduction must collapse these into fewer blocks.
            self.assertLess(len(lh_events), 32)

    def test_alberti_bass_reduces_to_one_event_per_beat(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.musicxml"
            fixtures.alberti_bass_score().write("musicxml", fp=str(input_path))
            out_dir = tmp_path / "out"

            result_path = music21_cmd.generate_simplified_musicxml_using_music21(
                str(input_path), out_dir=str(out_dir)
            )

            output_score = score_utils.load_score(result_path)
            rh_notes = list(output_score.parts[0].flatten().notes)
            self.assertEqual([n.pitch.nameWithOctave for n in rh_notes], ["C5", "C5"])

            # An Alberti pattern is already one note per beat; the beat-window
            # reduction must not lose or duplicate beats when it "reduces" it.
            lh_events = list(output_score.parts[-1].flatten().notesAndRests)
            self.assertEqual(len(lh_events), 8)

    def test_walking_bass_line_is_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.musicxml"
            fixtures.walking_bass_score().write("musicxml", fp=str(input_path))
            out_dir = tmp_path / "out"

            result_path = music21_cmd.generate_simplified_musicxml_using_music21(
                str(input_path), out_dir=str(out_dir)
            )

            output_score = score_utils.load_score(result_path)
            # A single-note-per-beat walking bass is already beginner-friendly;
            # the reduction must be a no-op rather than merging or dropping notes.
            lh_notes = list(output_score.parts[-1].flatten().notes)
            self.assertEqual(
                [n.pitch.nameWithOctave for n in lh_notes],
                ["C3", "D3", "E3", "F3", "G3", "A3", "B3", "C4"],
            )


if __name__ == "__main__":
    unittest.main()
