import unittest

from src.piano_learning.utils import musicxml_rewriter
from src.piano_learning.utils import simplification_plan

try:
    from music21 import chord
    from music21 import note
    from music21 import stream
except ImportError:  # pragma: no cover - depends on local music21 installation
    chord = None
    note = None
    stream = None


@unittest.skipIf(stream is None, "music21 is not installed")
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
