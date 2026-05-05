import json
import logging
from datetime import datetime
from pathlib import Path

import httpx

from src.piano_learning.commands import generate_analysis_of_musicxml
from src.piano_learning.utils import musicxml_rewriter
from src.piano_learning.utils import openai_utils
from src.piano_learning.utils import simplification_plan
from src.piano_learning.utils import template_utils

logger = logging.getLogger(__name__)

def _write_data_to_file_and_log(data_to_write: object, out_dir: Path, basename_prefix: str, basename_suffix: str, extension: str) -> Path:
    """
    Writes data to a file in out_dir with a name based on prefix and suffix.
    """
    # Save the data to a file for debugging
    path = out_dir / f"{basename_prefix}_{basename_suffix}.{extension}"
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data_to_write, (dict, list)):
            f.write(json.dumps(data_to_write, ensure_ascii=False, indent=2))
        else:
            f.write(openai_utils._coerce_to_text(data_to_write))
    logger.info(f"✅ {basename_suffix} saved to: {path}")
    return path

def generate_simplified_musicxml(
    musicxml_path: str,
    out_dir: Path,
    use_agent: bool = False,
) -> Path | None:
    """
    Generates a simplified MusicXML file from an OpenAI-produced LH plan.
    """
    try:
        # Save the simplified MusicXML to a new file
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
        p = Path(musicxml_path)
        basename = p.stem
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        resources_dir = Path(__file__).resolve().parents[1] / "resources"
        system_tpl = resources_dir / "system_instructions_for_chatgpt.j2"
        user_tpl = resources_dir / "user_prompt_for_chatgpt.j2"
        context = {"BASENAME": basename, "TIMESTAMP": timestamp}
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
        # write the prompts to a file for debugging
        _write_data_to_file_and_log(compact_analysis, out_dir, p.stem, "compact_analysis_for_plan", "json")
        _write_data_to_file_and_log(plan_schema, out_dir, p.stem, "simplification_plan_schema", "json")
        _write_data_to_file_and_log(system_prompt, out_dir, p.stem, "simplified_system_prompt", "txt")
        _write_data_to_file_and_log(query, out_dir, p.stem, "simplified_user_prompt", "txt")

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

        output_text = (output_text or "").strip()
        raw_plan = simplification_plan.extract_plan_json(output_text)
        plan = simplification_plan.validate_plan(
            raw_plan,
            source_measure_numbers=source_measure_numbers,
            require_all_measures=True,
        )
        musicxml_output_path = out_dir / f"{p.stem}_simplified.musicxml"
        musicxml_rewriter.write_simplified_musicxml_from_plan(
            musicxml_path,
            plan,
            musicxml_output_path,
        )

        # Save the all data to files for debugging
        _write_data_to_file_and_log(reasoning, out_dir, p.stem, "simplified_reasoning", "txt")
        _write_data_to_file_and_log(output_text, out_dir, p.stem, "simplification_plan_full_output", "txt")
        _write_data_to_file_and_log(plan, out_dir, p.stem, "simplification_plan", "json")

        return musicxml_output_path

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None

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
