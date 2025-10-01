import json
import logging
import re
from datetime import datetime
from pathlib import Path

import httpx

from src.piano_learning.commands import generate_analysis_of_musicxml
from src.utils import openai_utils
from src.utils import template_utils

logger = logging.getLogger(__name__)

def _minify_xml_preserving_text(xml: str) -> str:
    """
    Minify XML without altering text nodes:
    - Remove comments
    - Collapse whitespace between tags
    """
    xml = re.sub(r'<!--.*?-->', '', xml, flags=re.DOTALL)
    xml = re.sub(r'>\s+<', '><', xml)
    return xml.strip()

def _write_data_to_file_and_log(data_to_write: str, out_dir: Path, basename_prefix: str, basename_suffix: str, extension: str) -> Path:
    """
    Writes data to a file in out_dir with a name based on prefix and suffix.
    """
    # Save the data to a file for debugging
    path = out_dir / f"{basename_prefix}_{basename_suffix}.{extension}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(data_to_write)
    logger.info(f"✅ {basename_suffix} saved to: {path}")
    return path

def extract_simplified_musicxml(output_text: str) -> str:
    """
    Extracts the simplified MusicXML content from the model's output text.
    """
    # Extract the first XML code block
    xml_match = re.search(r"```xml\s*(.*?)\s*```", output_text, flags=re.DOTALL)
    if not xml_match:
        # Fallback: try any code fence
        xml_match = re.search(r"```\s*(.*?)\s*```", output_text, flags=re.DOTALL)
    if not xml_match:
        raise RuntimeError("Model response did not contain a MusicXML code block.")

    simplified_musicxml = xml_match.group(1).strip()
    return simplified_musicxml

def generate_simplified_musicxml(musicxml_path: str, out_dir: Path, use_agent: bool, run_model_response_in_background: bool) -> Path:
    """
    Generates a simplified version of a MusicXML file using an AI agent.
    """
    try:
        # Save the simplified MusicXML to a new file
        if not out_dir.exists():
            raise FileNotFoundError(f"Output directory does not exist: {out_dir}")
        if not out_dir.is_dir():
            raise NotADirectoryError(f"Output path is not a directory: {out_dir}")

        analysis = generate_analysis_of_musicxml.build_analysis_bundle(musicxml_path)
        analysis_compact_json = json.dumps(analysis, ensure_ascii=False, indent=None, separators=(',', ':'))
        with open(musicxml_path, encoding="utf-8") as f:
            musicxml_content = f.read()
        musicxml_content = _minify_xml_preserving_text(musicxml_content)

        # Prepare templated prompts
        p = Path(musicxml_path)
        basename = p.stem
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        resources_dir = Path(__file__).resolve().parents[1] / "piano_learning" / "resources"
        system_tpl = resources_dir / "system_instructions_for_chatgpt.j2"
        user_tpl = resources_dir / "user_prompt_for_chatgpt.j2"
        context = {"BASENAME": basename, "TIMESTAMP": timestamp}
        system_prompt = template_utils.render_template_file(system_tpl, context)
        user_prompt = template_utils.render_template_file(user_tpl, context)

        # Set up the OpenAI client
        timeout = httpx.Timeout(900.0, read=900.0, write=120.0, connect=60.0)
        query = (
            f"{user_prompt}\n\n"
            "Here is the MusicXML content (inline attachment):\n"
            "```xml\n"
            f"{musicxml_content}\n"
            "```\n\n"
            "Here is the harmony analysis JSON (inline attachment):\n"
            "```json\n"
            f"{analysis_compact_json}\n"
            "```\n"
        )
        # write the prompts to a file for debugging
        _write_data_to_file_and_log(musicxml_content, out_dir, p.stem, "original", "musicxml")
        _write_data_to_file_and_log(analysis_compact_json, out_dir, p.stem, "analysis", "json")
        _write_data_to_file_and_log(system_prompt, out_dir, p.stem, "simplified_system_prompt", "txt")
        _write_data_to_file_and_log(user_prompt, out_dir, p.stem, "simplified_user_prompt", "txt")

        # TODO: This isn't 100% working due to timeouts I don't know how to work around.
        if use_agent:
            output_text, reasoning = openai_utils.run_openai_response_with_agent(
                timeout=timeout,
                # TODO: GPT-5 isn't fully working with the agents library yet
                # model="gpt-5",
                model="gpt-5-mini",
                instructions=system_prompt,
                input_text=query,
                max_retries=2
            )
        elif run_model_response_in_background:
            output_text, reasoning = openai_utils.run_openai_response_in_background(
                timeout=timeout,
                model="gpt-5",
                instructions=system_prompt,
                input_text=query,
                poll_interval_seconds=60,
                max_retries=2
            )

        output_text = (output_text or "").strip()
        simplified_musicxml = extract_simplified_musicxml(output_text)

        # Save the all data to files for debugging
        _write_data_to_file_and_log(reasoning, out_dir, p.stem, "simplified_reasoning", "txt")
        _write_data_to_file_and_log(output_text, out_dir, p.stem, "simplified_full_output", "txt")
        musicxml_output_path = _write_data_to_file_and_log(simplified_musicxml, out_dir, p.stem, "simplified", "musicxml")

        return musicxml_output_path

    except Exception as e:
        logger.error(f"An error occurred: {e}")

def generate_chatgpt_prompts_for_simplified_musicxml(musicxml_path: str, out_dir: Path) -> None:
    """
    Generates ChatGPT prompts for a given MusicXML file and writes them to a single file in out_dir.
    Assumes out_dir already exists and is a directory (caller is responsible for creation).
    """
    base_for_prompts = Path('src/piano_learning/resources')
    base_file_name = Path(musicxml_path).stem
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ctx = {"BASENAME": base_file_name, "TIMESTAMP": timestamp}

    system_prompt = template_utils.render_template_file(base_for_prompts / 'system_instructions_for_chatgpt.j2', ctx)
    user_prompt = template_utils.render_template_file(base_for_prompts / 'user_prompt_for_chatgpt.j2', ctx)

    # Validate out_dir is provided by the caller and exists
    if not out_dir.exists():
        raise FileNotFoundError(f"Output directory does not exist: {out_dir}")
    if not out_dir.is_dir():
        raise NotADirectoryError(f"Output path is not a directory: {out_dir}")

    out_path = out_dir / f"{base_file_name}_{timestamp}_simplification_prompts.txt"
    content = (
        f"{system_prompt}\n\n"
        + "=" * 80 + "\n\n"
        f"{user_prompt}\n"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"✅ Prompts written to: {out_path}")
