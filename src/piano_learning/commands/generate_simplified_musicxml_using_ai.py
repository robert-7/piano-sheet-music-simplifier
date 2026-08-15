import json
import logging
from datetime import datetime
from pathlib import Path

import httpx

from src.piano_learning.commands import generate_analysis_of_musicxml
from src.piano_learning.utils import musicxml_rewriter
from src.piano_learning.utils import openai_utils
from src.piano_learning.utils import run_artifacts
from src.piano_learning.utils import simplification_plan
from src.piano_learning.utils import simplification_report
from src.piano_learning.utils import template_utils

logger = logging.getLogger(__name__)


def generate_simplified_musicxml(
    musicxml_path: str,
    out_dir: Path,
    use_agent: bool = False,
) -> Path:
    """
    Generates a simplified MusicXML file from an OpenAI-produced LH plan.

    Every run leaves a standardized artifact trail (see ``run_artifacts`` and
    ``docs/debugging-artifacts.md``): prompt inputs, the raw model output and
    reasoning (written *before* validation so a failed run is still inspectable),
    a validation report, the structured plan, the final MusicXML, a simplification
    report, and a ``run_summary.json`` written on both success and failure.
    """
    p = Path(musicxml_path)
    stem = p.stem

    # Request characteristics -- captured once so we can both log them and record
    # them in the run summary (issue #72).
    mode = "agent" if use_agent else "responses_background"
    model = openai_utils.OPENAI_AGENT_MODEL if use_agent else openai_utils.OPENAI_MODEL
    request_settings: dict[str, object] = {"timeoutSeconds": 900}
    if not use_agent:
        request_settings.update(
            {
                "maxOutputTokens": 24000,
                "reasoningEffort": "medium",
                "reasoningSummary": "detailed",
            }
        )
    logger.info(
        "OpenAI simplification request: mode=%s, model=%s, settings=%s",
        mode,
        model,
        request_settings,
    )

    # The full set of artifacts this backend can produce, in run order. The run
    # summary reports which of these actually made it to disk.
    artifact_roles = [
        "prompt_system",
        "prompt_user",
        "prompt_compact_analysis",
        "prompt_plan_schema",
        "model_output_raw",
        "model_reasoning",
        "validation_report",
        "plan",
        "simplified_musicxml",
        "simplification_report",
    ]

    outcome = "failed"
    error_message: str | None = None
    validation_state: dict[str, object] | None = None
    report_highlights: dict[str, object] | None = None

    try:
        if not out_dir.exists():
            raise FileNotFoundError(f"Output directory does not exist: {out_dir}")
        if not out_dir.is_dir():
            raise NotADirectoryError(f"Output path is not a directory: {out_dir}")

        analysis = generate_analysis_of_musicxml.build_analysis_bundle(musicxml_path)
        measure_grid = musicxml_rewriter.get_measure_grid(musicxml_path)
        source_measure_numbers = [entry["number"] for entry in measure_grid]
        compact_analysis = simplification_plan.compact_analysis_for_plan(
            analysis,
            measure_grid=measure_grid,
        )
        compact_analysis_json = json.dumps(compact_analysis, ensure_ascii=False, separators=(',', ':'))
        plan_schema = simplification_plan.get_plan_schema()
        plan_schema_json = json.dumps(plan_schema, ensure_ascii=False, separators=(',', ':'))

        # Prepare templated prompts
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        resources_dir = Path(__file__).resolve().parents[1] / "resources"
        system_tpl = resources_dir / "system_instructions_for_chatgpt.j2"
        user_tpl = resources_dir / "user_prompt_for_chatgpt.j2"
        context = {"BASENAME": stem, "TIMESTAMP": timestamp}
        system_prompt = template_utils.render_template_file(system_tpl, context)
        user_prompt = template_utils.render_template_file(user_tpl, context)

        timeout = httpx.Timeout(900.0, read=900.0, write=120.0, connect=60.0)
        query = (
            f"{user_prompt}\n\n"
            "Return JSON only. It must validate against this simplification-plan schema:\n"
            "```json\n"
            f"{plan_schema_json}\n"
            "```\n\n"
            "Here is the compact analysis JSON for LH planning:\n"
            "```json\n"
            f"{compact_analysis_json}\n"
            "```\n\n"
            "Do not emit MusicXML. Do not include prose outside the JSON object.\n"
        )
        # Persist prompt inputs (what was sent) before the API call.
        run_artifacts.write_artifact(out_dir, stem, "prompt_compact_analysis", compact_analysis)
        run_artifacts.write_artifact(out_dir, stem, "prompt_plan_schema", plan_schema)
        run_artifacts.write_artifact(out_dir, stem, "prompt_system", system_prompt)
        run_artifacts.write_artifact(out_dir, stem, "prompt_user", query)

        if use_agent:
            output_text, reasoning = openai_utils.run_openai_response_with_agent(
                timeout=timeout,
                model=openai_utils.OPENAI_AGENT_MODEL,
                instructions=system_prompt,
                input_text=query,
                max_retries=2,
            )
        else:
            output_text, reasoning = openai_utils.run_openai_response_in_background(
                timeout=timeout,
                model=openai_utils.OPENAI_MODEL,
                instructions=system_prompt,
                input_text=query,
                poll_interval_seconds=60,
                max_retries=2,
                max_output_tokens=24000,
                reasoning_effort="medium",
                reasoning_summary="detailed",
            )

        # Persist what came back *before* validating it. Previously these were
        # written only after a successful validate_plan, so a parse/validation
        # failure lost exactly the output needed to debug it (issue #72).
        output_text = (output_text or "").strip()
        run_artifacts.write_artifact(out_dir, stem, "model_output_raw", output_text)
        run_artifacts.write_artifact(out_dir, stem, "model_reasoning", reasoning)

        # Extract + validate, recording the outcome as a validation report either way.
        try:
            raw_plan = simplification_plan.extract_plan_json(output_text)
            plan = simplification_plan.validate_plan(
                raw_plan,
                source_measure_numbers=source_measure_numbers,
                require_all_measures=True,
            )
        except Exception as validation_exc:
            validation_state = {"status": "failed", "error": f"{type(validation_exc).__name__}: {validation_exc}"}
            run_artifacts.write_artifact(out_dir, stem, "validation_report", validation_state)
            raise
        validation_state = {"status": "passed", "error": None}
        run_artifacts.write_artifact(out_dir, stem, "validation_report", validation_state)
        run_artifacts.write_artifact(out_dir, stem, "plan", plan)

        musicxml_output_path = run_artifacts.artifact_path(out_dir, stem, "simplified_musicxml")
        musicxml_rewriter.write_simplified_musicxml_from_plan(
            musicxml_path,
            plan,
            musicxml_output_path,
        )

        # Make "nearly unmodified" output visible (issue #47): quantify how much
        # actually changed and warn loudly when a run barely touched the source.
        report = simplification_report.build_simplification_report(musicxml_path, plan)
        simplification_report.write_report(report, out_dir, stem)
        report_highlights = run_artifacts.report_highlights_from_report(report)
        if report["unmodifiedFlag"]:
            logger.warning("⚠️ Nearly unmodified output: %s", simplification_report.summary_line(report))
        else:
            logger.info("Simplification report: %s", simplification_report.summary_line(report))

        outcome = "success"
        return musicxml_output_path

    except Exception as exc:
        # Do not swallow failures into a silent None: a validation/parse/API
        # error is indistinguishable from "the model returned an unmodified
        # plan" if it disappears here. Log the full traceback for context and
        # re-raise so the caller (and the CLI process) fails loudly.
        error_message = f"{type(exc).__name__}: {exc}"
        logger.exception("Failed to generate simplified MusicXML from OpenAI plan.")
        raise
    finally:
        # Always leave a run summary -- especially on failure, where it is the
        # index to what was sent, what came back, and what failed validation.
        try:
            summary = run_artifacts.build_run_summary(
                input_source="musicxml",
                input_path=str(musicxml_path),
                stem=stem,
                simplifier="openai",
                outcome=outcome,
                out_dir=out_dir,
                mode=mode,
                model=model,
                request=request_settings,
                validation=validation_state,
                report_highlights=report_highlights,
                error=error_message,
                artifact_roles=artifact_roles,
            )
            run_artifacts.write_run_summary(out_dir, summary)
        except Exception:
            logger.exception("Failed to write run summary.")


def generate_chatgpt_prompts_for_simplified_musicxml(musicxml_path: str, out_dir: Path) -> None:
    """
    Generates ChatGPT prompts for a given MusicXML file and writes them to a single file in out_dir.
    Assumes out_dir already exists and is a directory (caller is responsible for creation).
    """
    base_for_prompts = Path(__file__).resolve().parents[1] / "resources"
    base_file_name = Path(musicxml_path).stem
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ctx = {"BASENAME": base_file_name, "TIMESTAMP": timestamp}

    system_prompt = template_utils.render_template_file(base_for_prompts / 'system_instructions_for_chatgpt.j2', ctx)
    user_prompt = template_utils.render_template_file(base_for_prompts / 'user_prompt_for_chatgpt.j2', ctx)
    analysis = generate_analysis_of_musicxml.build_analysis_bundle(musicxml_path)
    measure_grid = musicxml_rewriter.get_measure_grid(musicxml_path)
    compact_analysis = simplification_plan.compact_analysis_for_plan(analysis, measure_grid=measure_grid)
    plan_schema = simplification_plan.get_plan_schema()

    # Validate out_dir is provided by the caller and exists
    if not out_dir.exists():
        raise FileNotFoundError(f"Output directory does not exist: {out_dir}")
    if not out_dir.is_dir():
        raise NotADirectoryError(f"Output path is not a directory: {out_dir}")

    logger.info("OpenAI simplification request: mode=manual (prompt rendering only, no API call)")

    out_path = out_dir / f"{base_file_name}_{timestamp}_simplification_prompts.txt"
    content = (
        f"{system_prompt}\n\n"
        + "=" * 80 + "\n\n"
        f"{user_prompt}\n\n"
        "Return JSON only. It must validate against this simplification-plan schema:\n"
        "```json\n"
        f"{json.dumps(plan_schema, ensure_ascii=False, indent=2)}\n"
        "```\n\n"
        "Here is the compact analysis JSON for LH planning:\n"
        "```json\n"
        f"{json.dumps(compact_analysis, ensure_ascii=False, indent=2)}\n"
        "```\n\n"
        "Do not emit MusicXML. Do not include prose outside the JSON object.\n"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"✅ Prompts written to: {out_path}")

    # A run summary so the manual path is documented alongside the others. The
    # combined prompts file is not part of the standardized artifact map, so it
    # is not listed under artifacts here.
    summary = run_artifacts.build_run_summary(
        input_source="musicxml",
        input_path=str(musicxml_path),
        stem=base_file_name,
        simplifier="openai",
        outcome="success",
        out_dir=out_dir,
        mode="manual",
        artifact_roles=[],
    )
    run_artifacts.write_run_summary(out_dir, summary)
