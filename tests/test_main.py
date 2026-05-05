import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import main

REPO_ROOT = Path(__file__).resolve().parents[1]


class MainCliTests(unittest.TestCase):
    def test_resolve_log_level_defaults_to_info(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(main.resolve_log_level(), main.logging.INFO)

    def test_resolve_log_level_reads_env(self):
        with mock.patch.dict(os.environ, {"LOG_LEVEL": "debug"}, clear=True):
            self.assertEqual(main.resolve_log_level(), main.logging.DEBUG)

    def test_resolve_log_level_rejects_invalid_values(self):
        with mock.patch.dict(os.environ, {"LOG_LEVEL": "chatty"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Invalid LOG_LEVEL"):
                main.resolve_log_level()

    def test_import_main_without_openai_api_key(self):
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)

        result = subprocess.run(
            [sys.executable, "-c", "import main; print('ok')"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ok", result.stdout)

    def test_generate_simplified_musicxml_defaults_to_music21(self):
        parser = main.build_parser()

        args = parser.parse_args(["generate_simplified_musicxml", "user/input/example.musicxml"])

        self.assertEqual(main.resolve_simplifier(args), main.SIMPLIFIER_MUSIC21)
        main.validate_simplifier_args(args)

    def test_generate_simplified_musicxml_can_select_openai(self):
        parser = main.build_parser()

        args = parser.parse_args(
            [
                "generate_simplified_musicxml",
                "user/input/example.musicxml",
                "--simplifier",
                "openai",
            ]
        )

        self.assertEqual(main.resolve_simplifier(args), main.SIMPLIFIER_OPENAI)
        main.validate_simplifier_args(args)

    def test_manual_requires_openai_simplifier(self):
        parser = main.build_parser()

        args = parser.parse_args(
            [
                "generate_simplified_musicxml",
                "user/input/example.musicxml",
                "--manual",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--manual requires --simplifier openai."):
            main.validate_simplifier_args(args)

    def test_use_agent_requires_openai_simplifier(self):
        parser = main.build_parser()

        args = parser.parse_args(
            [
                "generate_simplified_musicxml",
                "user/input/example.musicxml",
                "--use-agent",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--use-agent requires --simplifier openai."):
            main.validate_simplifier_args(args)

    def test_generate_simplified_pdf_supports_openai_backend(self):
        parser = main.build_parser()

        args = parser.parse_args(
            [
                "generate_simplified_pdf",
                "--musicxml_path",
                "user/input/example.musicxml",
                "--simplifier",
                "openai",
                "--use-agent",
            ]
        )

        self.assertEqual(main.resolve_simplifier(args), main.SIMPLIFIER_OPENAI)
        main.validate_simplifier_args(args)

    def test_apply_simplification_plan_parser(self):
        parser = main.build_parser()

        args = parser.parse_args(
            [
                "apply_simplification_plan",
                "user/input/example.musicxml",
                "user/input/example_plan.json",
            ]
        )

        self.assertEqual(args.command, "apply_simplification_plan")
        self.assertEqual(args.musicxml_path, "user/input/example.musicxml")
        self.assertEqual(args.plan_path, "user/input/example_plan.json")

    def test_run_simplification_backend_dispatches_to_music21(self):
        music21_module = types.ModuleType("generate_simplified_musicxml_using_music21")
        music21_module.generate_simplified_musicxml_using_music21 = mock.Mock(return_value="music21-output.musicxml")

        with mock.patch.dict(
            sys.modules,
            {
                "src.piano_learning.commands.generate_simplified_musicxml_using_music21": music21_module,
            },
        ):
            result = main.run_simplification_backend(
                "user/input/example.musicxml",
                Path("user/output"),
                main.SIMPLIFIER_MUSIC21,
            )

        self.assertEqual(result, "music21-output.musicxml")
        music21_module.generate_simplified_musicxml_using_music21.assert_called_once()

    def test_run_simplification_backend_dispatches_to_openai(self):
        openai_module = types.ModuleType("generate_simplified_musicxml_using_ai")
        openai_module.generate_simplified_musicxml = mock.Mock(return_value="openai-output.musicxml")

        with mock.patch.dict(
            sys.modules,
            {
                "src.piano_learning.commands.generate_simplified_musicxml_using_ai": openai_module,
            },
        ):
            result = main.run_simplification_backend(
                "user/input/example.musicxml",
                Path("user/output"),
                main.SIMPLIFIER_OPENAI,
                use_agent=True,
            )

        self.assertEqual(result, "openai-output.musicxml")
        openai_module.generate_simplified_musicxml.assert_called_once_with(
            "user/input/example.musicxml",
            Path("user/output"),
            use_agent=True,
        )


if __name__ == "__main__":
    unittest.main()
