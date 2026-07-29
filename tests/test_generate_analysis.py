import copy
import unittest

from src.piano_learning.commands import generate_analysis_of_musicxml as gena

try:
    from music21 import chord
    from music21 import note
    from music21 import stream
except ImportError:  # pragma: no cover - depends on local music21 installation
    chord = None
    note = None
    stream = None


def _c_major_one_chord_score():
    """A single-measure score in C major containing one C-major triad."""
    score = stream.Score()
    part = stream.Part()
    measure = stream.Measure(number=1)
    measure.insert(0, chord.Chord(["C4", "E4", "G4"], quarterLength=4.0))
    part.append(measure)
    score.append(part)
    return score


@unittest.skipIf(stream is None, "music21 is not installed")
class ExtractHarmoniesTests(unittest.TestCase):
    def test_roman_numeral_is_populated_for_tonic_triad(self):
        # A C-major triad in C major must be analyzed as the tonic (I).
        # Before the fix, romanNumeralFromChord was called with an invalid
        # `keyStr=` kwarg, so it always raised and rn silently stayed None.
        score = _c_major_one_chord_score()

        events = gena.extract_harmonies(score)

        self.assertEqual(len(events), 1)
        self.assertIsNotNone(
            events[0].rn,
            "Roman numeral should be populated for a tonic triad in C major",
        )
        self.assertEqual(events[0].rn, "I")


if __name__ == "__main__":
    unittest.main()
