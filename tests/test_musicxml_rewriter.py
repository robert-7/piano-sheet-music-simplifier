import unittest

from music21 import chord
from music21 import clef
from music21 import note
from music21 import stream

from src.piano_learning.utils import musicxml_rewriter
from src.piano_learning.utils import simplification_plan


class LeftHandPartSelectionTests(unittest.TestCase):
    def test_raises_when_score_has_a_single_combined_part(self):
        score = stream.Score()
        combined = stream.Part()
        combined.append(stream.Measure(number=1))
        score.append(combined)

        with self.assertRaises(ValueError):
            musicxml_rewriter._left_hand_part(score)

    def test_raises_when_score_has_more_than_two_parts(self):
        score = stream.Score()
        for _ in range(3):
            part = stream.Part()
            part.append(stream.Measure(number=1))
            score.append(part)

        with self.assertRaises(ValueError):
            musicxml_rewriter._left_hand_part(score)

    def test_selects_bass_clef_part_when_staff_order_is_reversed(self):
        score = stream.Score()
        lh_first = stream.Part()
        lh_measure = stream.Measure(number=1)
        lh_measure.clef = clef.BassClef()
        lh_measure.insert(0, note.Note("C3"))
        lh_first.append(lh_measure)

        rh_second = stream.Part()
        rh_measure = stream.Measure(number=1)
        rh_measure.clef = clef.TrebleClef()
        rh_measure.insert(0, note.Note("C5"))
        rh_second.append(rh_measure)

        score.append(lh_first)
        score.append(rh_second)

        selected = musicxml_rewriter._left_hand_part(score)

        self.assertIs(selected, lh_first)


class MusicXmlRewriterTests(unittest.TestCase):
    def test_apply_plan_rewrites_only_last_part(self):
        score = stream.Score()
        rh = stream.Part()
        lh = stream.Part()

        rh_measure = stream.Measure(number=1)
        rh_measure.insert(0, note.Note("C4"))
        rh.append(rh_measure)

        lh_measure = stream.Measure(number=1)
        lh_voice = stream.Voice(id="5")
        lh_voice.insert(0, note.Note("C4"))
        lh_measure.insert(0, lh_voice)
        lh.append(lh_measure)

        score.append(rh)
        score.append(lh)

        plan = simplification_plan.validate_plan(
            {
                "schemaVersion": simplification_plan.PLAN_SCHEMA_VERSION,
                "scope": simplification_plan.PLAN_SCOPE,
                "measures": [
                    {
                        "number": 1,
                        "texture": "block",
                        "events": [
                            {"offset": 0.0, "duration": 1.0, "pitches": ["C3", "G3"]},
                        ],
                    }
                ],
            },
            source_measure_numbers=[1],
        )

        musicxml_rewriter.apply_plan_to_score(score, plan)

        rh_notes = list(score.parts[0].recurse().getElementsByClass(note.Note))
        lh_notes = list(score.parts[1].recurse().getElementsByClass(note.Note))
        lh_chords = list(score.parts[1].recurse().getElementsByClass(chord.Chord))
        self.assertEqual([n.nameWithOctave for n in rh_notes], ["C4"])
        self.assertEqual([n.nameWithOctave for n in lh_notes], [])
        self.assertEqual([[p.nameWithOctave for p in c.pitches] for c in lh_chords], [["C3", "G3"]])


if __name__ == "__main__":
    unittest.main()
