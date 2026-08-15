import tempfile
import unittest
from pathlib import Path

from music21 import chord
from music21 import note
from music21 import stream

from src.piano_learning.utils import simplification_report


def _measure(number, changed, plan_texture, source_notes, plan_notes, **extra):
    entry = {
        "number": number,
        "changed": changed,
        "planTexture": plan_texture,
        "sourceNoteCount": source_notes,
        "planNoteCount": plan_notes,
    }
    entry.update(extra)
    return entry


class SummarizeMeasuresTests(unittest.TestCase):
    def test_counts_and_percentages(self):
        per_measure = [
            _measure(1, True, "block", 8, 3),
            _measure(2, False, "preserve", 4, 4),
            _measure(3, False, "preserve", 4, 4),
            _measure(4, True, "dyad", 6, 2),
        ]

        report = simplification_report.summarize_measures(per_measure)

        self.assertEqual(report["measuresTotal"], 4)
        self.assertEqual(report["measuresChanged"], 2)
        self.assertEqual(report["measuresPreserved"], 2)
        self.assertEqual(report["pctChanged"], 50.0)
        self.assertFalse(report["unmodifiedFlag"])
        self.assertEqual(report["textureHistogram"], {"block": 1, "preserve": 2, "dyad": 1})
        self.assertEqual(report["lhNoteCountDelta"], {"source": 22, "plan": 13, "delta": -9})

    def test_unmodified_flag_trips_when_few_measures_change(self):
        per_measure = [_measure(n, False, "preserve", 4, 4) for n in range(1, 11)]
        per_measure.append(_measure(11, True, "block", 8, 3))

        report = simplification_report.summarize_measures(per_measure)

        # 1 of 11 changed = ~9.09% which is at/below the 10% threshold.
        self.assertTrue(report["unmodifiedFlag"])
        self.assertLessEqual(report["pctChanged"], simplification_report.UNMODIFIED_PCT_THRESHOLD)

    def test_empty_report_is_safe(self):
        report = simplification_report.summarize_measures([])

        self.assertEqual(report["measuresTotal"], 0)
        self.assertEqual(report["pctChanged"], 0.0)
        self.assertFalse(report["unmodifiedFlag"])

    def test_recommendation_tracking_included_when_present(self):
        per_measure = [
            _measure(1, True, "block", 8, 3, recommendationFollowed=True),
            _measure(2, False, "preserve", 4, 4, recommendationFollowed=False),
        ]

        report = simplification_report.summarize_measures(per_measure)

        self.assertEqual(report["recommendationsFollowed"], 1)
        self.assertEqual(report["recommendationsOverridden"], 1)

    def test_summary_line_is_human_readable(self):
        report = simplification_report.summarize_measures(
            [_measure(1, True, "block", 8, 3)]
        )

        line = simplification_report.summary_line(report)

        self.assertIn("1/1 measures changed", line)
        self.assertIn("LH note delta -5", line)


class DiffReportsTests(unittest.TestCase):
    def test_diff_surfaces_texture_divergence(self):
        report_a = simplification_report.summarize_measures(
            [
                _measure(1, True, "block", 8, 3),
                _measure(2, False, "preserve", 4, 4),
            ]
        )
        report_b = simplification_report.summarize_measures(
            [
                _measure(1, True, "block", 8, 3),
                _measure(2, True, "dyad", 4, 2),
            ]
        )

        diff = simplification_report.diff_reports(report_a, report_b)

        self.assertEqual(diff["divergentMeasures"], [{"number": 2, "a": "preserve", "b": "dyad"}])
        self.assertEqual(diff["pctChanged"], {"a": 50.0, "b": 100.0})


class BuildReportFromScoreTests(unittest.TestCase):
    def _write_busy_score(self, directory: Path) -> Path:
        """A 2-part score whose LH is a busy sixteenth-note broken arpeggio."""
        score = stream.Score()
        rh = stream.Part()
        lh = stream.Part()

        rh_measure = stream.Measure(number=1)
        rh_measure.insert(0, note.Note("C5", quarterLength=4.0))
        rh.append(rh_measure)

        lh_measure = stream.Measure(number=1)
        for i, name in enumerate(["C2", "G2", "C3", "E3", "G3", "C4", "E4", "G4"]):
            lh_measure.insert(i * 0.25, note.Note(name, quarterLength=0.25))
        lh.append(lh_measure)

        score.append(rh)
        score.append(lh)

        path = directory / "busy.musicxml"
        score.write("musicxml", fp=str(path))
        return path

    def test_report_marks_block_measure_as_changed_and_simpler(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = self._write_busy_score(Path(tmp))
            plan = {
                "schemaVersion": "lh-simplification-plan/v1",
                "scope": "left-hand-only",
                "measures": [
                    {
                        "number": 1,
                        "texture": "block",
                        "events": [{"offset": 0.0, "duration": 4.0, "pitches": ["C2", "G2"]}],
                    }
                ],
            }

            report = simplification_report.build_simplification_report(source_path, plan)

        self.assertEqual(report["measuresChanged"], 1)
        self.assertTrue(report["perMeasure"][0]["changed"])
        # LH went from 8 sixteenths to a single 2-note block chord.
        self.assertEqual(report["lhNoteCountDelta"]["delta"], -6)
        # The plan chose block, which matches the prescriptive recommendation.
        self.assertEqual(report["recommendationsFollowed"], 1)
        self.assertEqual(report["recommendationsOverridden"], 0)

    def test_report_flags_unmodified_when_plan_preserves_busy_measure(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = self._write_busy_score(Path(tmp))
            plan = {
                "schemaVersion": "lh-simplification-plan/v1",
                "scope": "left-hand-only",
                "measures": [{"number": 1, "texture": "preserve", "events": []}],
            }

            report = simplification_report.build_simplification_report(source_path, plan)

        self.assertTrue(report["unmodifiedFlag"])
        self.assertEqual(report["measuresChanged"], 0)
        # Preserving a measure the analysis recommended simplifying is an override.
        self.assertEqual(report["recommendationsOverridden"], 1)


def _write_score(directory: Path, filename: str, lh_builder) -> Path:
    """Write a 2-part, 1-measure score whose LH measure is filled by ``lh_builder``."""
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

    path = directory / filename
    score.write("musicxml", fp=str(path))
    return path


def _alberti_style_measure(measure):
    """Eight eighth notes, 2 pitch classes/beat -> 8 sounding notes total."""
    for i, name in enumerate(["C2", "G2", "E2", "G2", "C2", "G2", "E2", "G2"]):
        measure.insert(i * 0.5, note.Note(name, quarterLength=0.5))


def _same_count_block_measure(measure):
    """Four 2-note block chords -> 8 sounding notes total, same as the Alberti source."""
    for i, pitches in enumerate([("C2", "G2"), ("C2", "E2"), ("C2", "G2"), ("C2", "E2")]):
        measure.insert(i * 1.0, chord.Chord(list(pitches), quarterLength=1.0))


class BuildMusic21ReportTests(unittest.TestCase):
    def test_same_note_count_reduction_is_still_marked_changed(self):
        # A reduction can rearrange notes into the same total count (e.g. an
        # Alberti figure collapsed into same-count block chords). Note-count
        # equality alone would misreport this as "preserve"; the report must
        # compare actual content instead.
        with tempfile.TemporaryDirectory() as tmp:
            source_path = _write_score(Path(tmp), "source.musicxml", _alberti_style_measure)
            simplified_path = _write_score(Path(tmp), "simplified.musicxml", _same_count_block_measure)

            report = simplification_report.build_music21_report(source_path, simplified_path)

        entry = report["perMeasure"][0]
        self.assertEqual(entry["sourceNoteCount"], entry["planNoteCount"])
        self.assertTrue(entry["changed"])
        self.assertEqual(report["measuresChanged"], 1)

    def test_identical_measure_is_marked_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = _write_score(Path(tmp), "source.musicxml", _alberti_style_measure)
            identical_path = _write_score(Path(tmp), "identical.musicxml", _alberti_style_measure)

            report = simplification_report.build_music21_report(source_path, identical_path)

        self.assertFalse(report["perMeasure"][0]["changed"])
        self.assertEqual(report["measuresChanged"], 0)


class WriteAndLoadReportTests(unittest.TestCase):
    def test_write_report_round_trips_through_load_report(self):
        report = simplification_report.summarize_measures([_measure(1, True, "block", 8, 3)])

        with tempfile.TemporaryDirectory() as tmp:
            written_path = simplification_report.write_report(report, tmp, "song")

            self.assertEqual(written_path.name, "song_simplification_report.json")
            self.assertEqual(simplification_report.load_report(written_path), report)
            # A directory is also accepted; it should find the same file.
            self.assertEqual(simplification_report.load_report(tmp), report)


if __name__ == "__main__":
    unittest.main()
