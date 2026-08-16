import unittest

from src.piano_learning.utils import simplification_plan


def valid_plan() -> dict:
    return {
        "schemaVersion": simplification_plan.PLAN_SCHEMA_VERSION,
        "scope": simplification_plan.PLAN_SCOPE,
        "summary": "Block dyads on every beat.",
        "measures": [
            {
                "number": 1,
                "texture": "block",
                "events": [
                    {"offset": 0.0, "duration": 1.0, "pitches": ["C3", "G3"]},
                    {"offset": 1.0, "duration": 1.0, "pitches": ["E3", "G3"]},
                ],
            },
            {
                "number": 2,
                "texture": "rest",
                "events": [
                    {"offset": 0.0, "duration": 3.0, "rest": True},
                ],
            },
        ],
    }


class SimplificationPlanTests(unittest.TestCase):
    def test_extract_plan_json_from_fenced_output(self):
        text = """```json
{"schemaVersion":"lh-simplification-plan/v1","scope":"left-hand-only","measures":[{"number":1,"texture":"rest","events":[{"offset":0,"duration":1,"rest":true}]}]}
```"""

        plan = simplification_plan.extract_plan_json(text)

        self.assertEqual(plan["schemaVersion"], simplification_plan.PLAN_SCHEMA_VERSION)
        self.assertEqual(plan["measures"][0]["number"], 1)

    def test_validate_plan_normalizes_and_checks_source_measures(self):
        plan = simplification_plan.validate_plan(
            valid_plan(),
            source_measure_numbers=[1, 2],
            measure_durations_by_number={1: 2.0, 2: 3.0},
        )

        self.assertEqual([measure["number"] for measure in plan["measures"]], [1, 2])
        self.assertEqual(plan["measures"][1]["events"][0]["rest"], True)

    def test_validate_plan_rejects_missing_measure(self):
        with self.assertRaisesRegex(ValueError, "missing source measures"):
            simplification_plan.validate_plan(
                valid_plan(),
                source_measure_numbers=[1, 2, 3],
            )

    def test_validate_plan_rejects_extra_measure(self):
        with self.assertRaisesRegex(ValueError, "non-source measures"):
            simplification_plan.validate_plan(
                valid_plan(),
                source_measure_numbers=[1],
            )

    def test_validate_plan_accepts_pickup_measure_zero(self):
        # Regression: pickup/anacrusis measures are conventionally numbered 0.
        # The validator previously rejected any measure number <= 0, which made
        # it impossible to ever produce a valid plan for a piece with a pickup.
        plan = valid_plan()
        plan["measures"].append(
            {
                "number": 0,
                "texture": "singleBass",
                "events": [{"offset": 0.0, "duration": 1.0, "pitches": ["C2"]}],
            }
        )

        normalized = simplification_plan.validate_plan(
            plan,
            source_measure_numbers=[0, 1, 2],
            measure_durations_by_number={0: 1.0, 1: 2.0, 2: 3.0},
        )

        self.assertEqual([measure["number"] for measure in normalized["measures"]], [0, 1, 2])

    def test_validate_plan_rejects_negative_measure_number(self):
        plan = valid_plan()
        plan["measures"][0]["number"] = -1

        with self.assertRaisesRegex(ValueError, "Invalid measure number"):
            simplification_plan.validate_plan(plan)

    def test_validate_plan_rejects_short_lh_duration(self):
        plan = valid_plan()
        plan["measures"][0]["events"][0]["duration"] = 0.25

        with self.assertRaisesRegex(ValueError, "shorter than an eighth note"):
            simplification_plan.validate_plan(plan)

    def test_validate_plan_rejects_too_many_simultaneous_notes(self):
        plan = valid_plan()
        plan["measures"][0]["events"][0]["pitches"] = ["C3", "E3", "G3", "B3"]

        with self.assertRaisesRegex(ValueError, "more than 3 pitches"):
            simplification_plan.validate_plan(plan)

    def test_validate_plan_rejects_events_past_measure_duration(self):
        plan = valid_plan()

        with self.assertRaisesRegex(ValueError, "exceeds source duration"):
            simplification_plan.validate_plan(
                plan,
                source_measure_numbers=[1, 2],
                measure_durations_by_number={1: 1.0, 2: 3.0},
            )

    def test_validate_plan_rejects_timing_gaps_when_duration_is_known(self):
        plan = valid_plan()

        with self.assertRaisesRegex(ValueError, "does not cover the full source duration"):
            simplification_plan.validate_plan(
                plan,
                source_measure_numbers=[1, 2],
                measure_durations_by_number={1: 3.0, 2: 3.0},
            )

    def test_extract_plan_json_rejects_truncation_markers(self):
        with self.assertRaisesRegex(ValueError, "truncation marker"):
            simplification_plan.extract_plan_json('{"schemaVersion":"lh-simplification-plan/v1"} ...')

    def test_extract_plan_json_allows_ellipsis_inside_string_values(self):
        # Regression for #81: a complete plan whose summary contains an ellipsis
        # must not be misread as truncated. Previously "..." was matched anywhere
        # in the raw output, so legitimate content was rejected.
        text = (
            '{"schemaVersion":"lh-simplification-plan/v1","scope":"left-hand-only",'
            '"summary":"LH reduced to block dyads on strong beats...",'
            '"measures":[{"number":1,"texture":"rest",'
            '"events":[{"offset":0,"duration":1,"rest":true}]}]}'
        )

        plan = simplification_plan.extract_plan_json(text)

        self.assertEqual(plan["summary"], "LH reduced to block dyads on strong beats...")
        self.assertEqual(plan["measures"][0]["number"], 1)

    def test_compact_analysis_keeps_only_plan_relevant_fields(self):
        analysis = {
            "metadata": {"timeSignatures": [{"mStart": 1, "sig": "3/4"}]},
            "keys": [{"mStart": 1, "localKey": "C major"}],
            "harmonies": [{"offset": 0, "qLen": 3, "root": "C"}],
            "melody": [{"offset": 0, "pitch": "C5"}],
            "bassline": [{"offset": 0, "pitch": "C3"}],
            "textureLH": [{"mRange": [1, 2], "pattern": "brokenArpeggio"}],
            "nctMask": [{"offset": 0, "keep": True}],
            "ranges": {"LH": {"low": "C2"}, "RH": {"high": "C6"}},
        }

        compact = simplification_plan.compact_analysis_for_plan(
            analysis,
            measure_grid=[{"number": 1, "duration": 3.0, "beatDuration": 1.0}],
        )

        self.assertIn("harmonies", compact)
        self.assertIn("measureGrid", compact)
        self.assertNotIn("melody", compact)
        self.assertNotIn("nctMask", compact)
        self.assertEqual(compact["ranges"], {"LH": {"low": "C2"}})

    def test_compact_analysis_keeps_prescriptive_recommendations(self):
        analysis = {
            "textureLH": [{"mRange": [1, 1], "pattern": "brokenArpeggio"}],
            "prescriptiveLH": [
                {"number": 1, "shouldSimplify": True, "targetTexture": "block", "authority": "recommend"}
            ],
        }

        compact = simplification_plan.compact_analysis_for_plan(
            analysis,
            measure_grid=[{"number": 1, "duration": 4.0, "beatDuration": 1.0}],
        )

        self.assertIn("prescriptiveLH", compact)
        self.assertEqual(compact["prescriptiveLH"][0]["targetTexture"], "block")

    def test_compact_analysis_drops_empty_prescriptive(self):
        compact = simplification_plan.compact_analysis_for_plan(
            {"harmonies": [{"offset": 0, "qLen": 4, "root": "C"}]},
            measure_grid=[{"number": 1, "duration": 4.0, "beatDuration": 1.0}],
        )

        self.assertNotIn("prescriptiveLH", compact)


if __name__ == "__main__":
    unittest.main()
