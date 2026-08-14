import copy
import unittest

from music21 import chord
from music21 import note
from music21 import stream

from src.piano_learning.commands import generate_analysis_of_musicxml as gena


def _c_major_one_chord_score():
    """A single-measure score in C major containing one C-major triad."""
    score = stream.Score()
    part = stream.Part()
    measure = stream.Measure(number=1)
    measure.insert(0, chord.Chord(["C4", "E4", "G4"], quarterLength=4.0))
    part.append(measure)
    score.append(part)
    return score


def _two_hand_score(lh_builder):
    """Build a 2-part score; ``lh_builder(measure)`` fills the LH measure 1."""
    score = stream.Score()
    rh = stream.Part()
    lh = stream.Part()

    rh_measure = stream.Measure(number=1)
    rh_measure.insert(0, note.Note("C5", quarterLength=4.0))
    rh.append(rh_measure)

    lh_measure = stream.Measure(number=1)
    lh_builder(lh_measure)
    lh.append(lh_measure)

    score.append(rh)
    score.append(lh)
    return score


def _busy_broken_arpeggio_measure(measure):
    """Eight ascending sixteenth notes -> brokenArpeggio at sixteenth density."""
    for i, name in enumerate(["C2", "G2", "C3", "E3", "G3", "C4", "E4", "G4"]):
        n = note.Note(name, quarterLength=0.25)
        measure.insert(i * 0.25, n)


def _simple_block_measure(measure):
    """A single sustained block chord -> already beginner-appropriate."""
    measure.insert(0, chord.Chord(["C2", "G2"], quarterLength=4.0))


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


class PrescriptiveAnalysisTests(unittest.TestCase):
    def test_busy_broken_arpeggio_is_recommended_for_block(self):
        score = _two_hand_score(_busy_broken_arpeggio_measure)

        recommendations = gena.build_prescriptive_analysis(score)

        self.assertEqual(len(recommendations), 1)
        recommendation = recommendations[0]
        self.assertTrue(recommendation.shouldSimplify)
        self.assertEqual(recommendation.targetTexture, "block")
        self.assertEqual(recommendation.authority, "recommend")
        self.assertGreater(recommendation.confidence, 0.5)

    def test_simple_block_is_preserved(self):
        score = _two_hand_score(_simple_block_measure)

        recommendations = gena.build_prescriptive_analysis(score)

        self.assertEqual(len(recommendations), 1)
        self.assertFalse(recommendations[0].shouldSimplify)
        self.assertEqual(recommendations[0].targetTexture, "preserve")

    def test_single_part_score_has_no_recommendations(self):
        # No distinct LH part means nothing to recommend.
        self.assertEqual(gena.build_prescriptive_analysis(_c_major_one_chord_score()), [])

    def test_bundle_includes_prescriptive_key(self):
        # build_analysis_bundle wires prescriptiveLH into the JSON bundle.
        recommendations = gena.build_prescriptive_analysis(_two_hand_score(_busy_broken_arpeggio_measure))
        self.assertTrue(all(r.authority == "recommend" for r in recommendations))


if __name__ == "__main__":
    unittest.main()
