"""
Tests for run-artifact naming, writing, and the per-run summary (issue #72).

These are deliberately pure/lightweight: no music21, no OpenAI. They lock in the
artifact filename map (so load-bearing names can't drift silently) and the
``run_summary.json`` structure a developer relies on to see what a run did.
"""
import json
import tempfile
import unittest
from pathlib import Path

from src.piano_learning.utils import run_artifacts


class ArtifactNamingTests(unittest.TestCase):
    def test_filename_for_each_role_is_stem_prefixed(self):
        # Every role produces a flat, stem-prefixed name in the output dir.
        expected = {
            "prompt_system": "Song_prompt_system.txt",
            "prompt_user": "Song_prompt_user.txt",
            "prompt_compact_analysis": "Song_prompt_compact_analysis.json",
            "prompt_plan_schema": "Song_prompt_plan_schema.json",
            "model_output_raw": "Song_model_output_raw.txt",
            "model_reasoning": "Song_model_reasoning.txt",
            "plan": "Song_simplification_plan.json",
            "validation_report": "Song_validation_report.json",
            # Load-bearing names (consumed by run_e2e.sh / compare_runs). These
            # assertions are a guard: renaming them breaks external consumers.
            "analysis": "Song_analysis.json",
            "simplified_musicxml": "Song_simplified.musicxml",
            "simplification_report": "Song_simplification_report.json",
        }
        for role, filename in expected.items():
            self.assertEqual(run_artifacts.artifact_filename("Song", role), filename)

    def test_all_registered_roles_are_covered_by_test(self):
        # If a new role is added to the registry, force a conscious test update.
        self.assertEqual(
            set(run_artifacts.ARTIFACT_SPECS),
            {
                "prompt_system",
                "prompt_user",
                "prompt_compact_analysis",
                "prompt_plan_schema",
                "model_output_raw",
                "model_reasoning",
                "plan",
                "validation_report",
                "analysis",
                "simplified_musicxml",
                "simplification_report",
            },
        )

    def test_unknown_role_raises(self):
        with self.assertRaises(KeyError):
            run_artifacts.artifact_filename("Song", "not_a_role")

    def test_artifact_path_joins_out_dir(self):
        path = run_artifacts.artifact_path(Path("/tmp/run"), "Song", "plan")
        self.assertEqual(path, Path("/tmp/run/Song_simplification_plan.json"))

    def test_repair_attempt_filename_is_reserved_and_zero_padded(self):
        # Repair (#70) is not implemented; the name is reserved + documented so
        # the future flow slots into the same layout without another rename.
        self.assertEqual(
            run_artifacts.repair_attempt_filename("Song", 1),
            "Song_repair_attempt_01.json",
        )
        self.assertEqual(
            run_artifacts.repair_attempt_filename("Song", 12),
            "Song_repair_attempt_12.json",
        )


class WriteArtifactTests(unittest.TestCase):
    def test_writes_json_for_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            path = run_artifacts.write_artifact(out_dir, "Song", "plan", {"measures": [1, 2]})
            self.assertEqual(path.name, "Song_simplification_plan.json")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"measures": [1, 2]})

    def test_writes_text_for_str(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            path = run_artifacts.write_artifact(out_dir, "Song", "model_reasoning", "hello\nworld")
            self.assertEqual(path.name, "Song_model_reasoning.txt")
            self.assertEqual(path.read_text(encoding="utf-8"), "hello\nworld")

    def test_coerces_non_string_scalars_to_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = run_artifacts.write_artifact(Path(tmp), "Song", "model_output_raw", 123)
            self.assertEqual(path.read_text(encoding="utf-8"), "123")


class RunSummaryTests(unittest.TestCase):
    def _touch(self, out_dir: Path, stem: str, roles: list[str]) -> None:
        for role in roles:
            (out_dir / run_artifacts.artifact_filename(stem, role)).write_text("x", encoding="utf-8")

    def test_report_highlights_extracts_key_fields(self):
        report = {
            "measuresTotal": 20,
            "measuresChanged": 12,
            "pctChanged": 60.0,
            "unmodifiedFlag": False,
            "lhNoteCountDelta": {"source": 100, "plan": 60, "delta": -40},
            "perMeasure": [{"number": 1}],  # dropped from highlights
        }
        highlights = run_artifacts.report_highlights_from_report(report)
        self.assertEqual(
            highlights,
            {
                "measuresTotal": 20,
                "measuresChanged": 12,
                "pctChanged": 60.0,
                "lhNoteDelta": -40,
                "unmodifiedFlag": False,
            },
        )
        self.assertNotIn("perMeasure", highlights)

    def test_build_summary_success_has_expected_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            roles = [
                "prompt_system",
                "prompt_user",
                "model_output_raw",
                "plan",
                "validation_report",
                "simplified_musicxml",
                "simplification_report",
            ]
            self._touch(out_dir, "Song", roles)

            summary = run_artifacts.build_run_summary(
                input_source="musicxml",
                input_path="user/input/Song.musicxml",
                stem="Song",
                simplifier="openai",
                outcome="success",
                out_dir=out_dir,
                mode="responses_background",
                model="gpt-5.5",
                request={"maxOutputTokens": 24000, "reasoningEffort": "medium"},
                validation={"status": "passed", "error": None},
                report_highlights={"pctChanged": 60.0, "unmodifiedFlag": False},
                artifact_roles=roles,
            )

            self.assertEqual(summary["schemaVersion"], run_artifacts.SCHEMA_VERSION)
            self.assertEqual(summary["input"], {"source": "musicxml", "path": "user/input/Song.musicxml", "stem": "Song"})
            self.assertEqual(summary["simplifier"], "openai")
            self.assertEqual(summary["mode"], "responses_background")
            self.assertEqual(summary["model"], "gpt-5.5")
            self.assertEqual(summary["request"]["maxOutputTokens"], 24000)
            self.assertEqual(summary["outcome"], "success")
            self.assertIsNone(summary["error"])
            self.assertEqual(summary["validation"]["status"], "passed")
            # Artifact map: every requested role listed, all present here.
            by_role = {entry["role"]: entry for entry in summary["artifacts"]}
            self.assertEqual(set(by_role), set(roles))
            self.assertTrue(all(entry["exists"] for entry in summary["artifacts"]))
            self.assertEqual(by_role["plan"]["file"], "Song_simplification_plan.json")

    def test_build_summary_failure_marks_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            # A failed run wrote prompts + raw output, but never a valid plan.
            self._touch(out_dir, "Song", ["prompt_system", "model_output_raw", "validation_report"])
            roles = ["prompt_system", "model_output_raw", "validation_report", "plan", "simplified_musicxml"]

            summary = run_artifacts.build_run_summary(
                input_source="musicxml",
                input_path="user/input/Song.musicxml",
                stem="Song",
                simplifier="openai",
                outcome="failed",
                out_dir=out_dir,
                mode="responses_background",
                model="gpt-5.5",
                validation={"status": "failed", "error": "measure 3 missing events"},
                error="ValueError: measure 3 missing events",
                artifact_roles=roles,
            )

            self.assertEqual(summary["outcome"], "failed")
            self.assertEqual(summary["error"], "ValueError: measure 3 missing events")
            self.assertEqual(summary["validation"]["status"], "failed")
            by_role = {entry["role"]: entry for entry in summary["artifacts"]}
            self.assertTrue(by_role["model_output_raw"]["exists"])
            self.assertFalse(by_role["plan"]["exists"])
            self.assertFalse(by_role["simplified_musicxml"]["exists"])

    def test_music21_summary_omits_openai_only_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            roles = ["simplified_musicxml", "simplification_report"]
            summary = run_artifacts.build_run_summary(
                input_source="musicxml",
                input_path="user/input/Song.musicxml",
                stem="Song",
                simplifier="music21",
                outcome="success",
                out_dir=out_dir,
                mode="local",
                artifact_roles=roles,
            )
            self.assertEqual(summary["simplifier"], "music21")
            self.assertEqual(summary["mode"], "local")
            self.assertIsNone(summary["model"])
            self.assertNotIn("request", summary)
            self.assertNotIn("validation", summary)

    def test_write_and_reload_run_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            summary = run_artifacts.build_run_summary(
                input_source="pdf",
                input_path="user/input/Song.pdf",
                stem="Song",
                simplifier="music21",
                outcome="success",
                out_dir=out_dir,
                mode="local",
                artifact_roles=["simplified_musicxml"],
            )
            path = run_artifacts.write_run_summary(out_dir, summary)
            self.assertEqual(path.name, run_artifacts.RUN_SUMMARY_FILENAME)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), summary)

    def test_summary_log_line_mentions_outcome_and_backend(self):
        summary = run_artifacts.build_run_summary(
            input_source="musicxml",
            input_path="user/input/Song.musicxml",
            stem="Song",
            simplifier="openai",
            outcome="success",
            out_dir="/tmp/does-not-need-to-exist",
            mode="responses_background",
            model="gpt-5.5",
            report_highlights={"pctChanged": 60.0, "unmodifiedFlag": False},
            artifact_roles=[],
        )
        line = run_artifacts.summary_log_line(summary)
        self.assertIn("success", line)
        self.assertIn("openai", line)


if __name__ == "__main__":
    unittest.main()
