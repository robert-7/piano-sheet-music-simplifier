import tempfile
import unittest
from pathlib import Path

from music21 import chord
from music21 import note
from music21 import stream

from src.piano_learning.commands import generate_simplified_musicxml_using_music21 as music21_cmd
from src.piano_learning.utils import score_utils


def _two_hand_score():
    """A 2-measure, 2-part score with a busy, arpeggiated LH to simplify."""
    score = stream.Score()
    rh = stream.Part()
    lh = stream.Part()

    for number in (1, 2):
        rh_measure = stream.Measure(number=number)
        rh_measure.insert(0, note.Note("C5", quarterLength=4.0))
        rh.append(rh_measure)

        lh_measure = stream.Measure(number=number)
        # A full-measure broken-arpeggio pattern: 4 sixteenth notes per beat,
        # so the beat-window reduction has something to collapse.
        pattern = ["C2", "G2", "C3", "E3"] * 4
        for i, name in enumerate(pattern):
            lh_measure.insert(i * 0.25, note.Note(name, quarterLength=0.25))
        lh.append(lh_measure)

    score.append(rh)
    score.append(lh)
    return score


class GenerateSimplifiedMusicxmlUsingMusic21Tests(unittest.TestCase):
    def test_happy_path_writes_musicxml_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.musicxml"
            _two_hand_score().write("musicxml", fp=str(input_path))
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
            _two_hand_score().write("musicxml", fp=str(input_path))
            out_dir = tmp_path / "out"

            result_path = music21_cmd.generate_simplified_musicxml_using_music21(
                str(input_path), out_dir=str(out_dir)
            )

            output_score = score_utils.load_score(result_path)
            lh_events = list(output_score.parts[-1].flatten().notesAndRests)
            # Source LH had 16 sixteenth-note events per measure (32 total);
            # the beat-window reduction must collapse these into fewer blocks.
            self.assertLess(len(lh_events), 32)


if __name__ == "__main__":
    unittest.main()
