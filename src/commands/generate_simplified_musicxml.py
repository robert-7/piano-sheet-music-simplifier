import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import dotenv
import httpx
import openai
from agents import Agent
from agents import function_tool
from agents import Runner
from agents import set_default_openai_client

from src.commands import generate_analysis_of_musicxml
from src.utils import score_utils
from src.utils.template_utils import render_template_file

logger = logging.getLogger(__name__)

dotenv.load_dotenv(dotenv_path=dotenv.find_dotenv(usecwd=True), override=False)

def _get_required_env(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(
                f"Missing required environment variable: {name}. "
                "Create a .env file in your project root with this key, or set it in your shell."
            )
        return value

OPENAI_API_KEY = _get_required_env("OPENAI_API_KEY")

def _minify_xml_preserving_text(xml: str) -> str:
    """
    Minify XML without altering text nodes:
    - Remove comments
    - Collapse whitespace between tags
    """
    xml = re.sub(r'<!--.*?-->', '', xml, flags=re.DOTALL)
    xml = re.sub(r'>\s+<', '><', xml)
    return xml.strip()

def generate_simplified_musicxml(musicxml_path: str) -> None:
    """
    Generates a simplified version of a MusicXML file using an AI agent.
    """
    try:
        analysis = generate_analysis_of_musicxml.build_analysis_bundle(musicxml_path)
        analysis_json = json.dumps(analysis, ensure_ascii=False, indent=None, separators=(',', ':'))
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
        system_prompt = render_template_file(system_tpl, context)
        user_prompt = render_template_file(user_tpl, context)

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
            f"{analysis_json}\n"
            "```\n"
        )
        logger.debug(query)
        if False:
            client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=timeout, max_retries=5)
            set_default_openai_client(client)
            code_execution_agent = Agent(
                name="Expert Piano Arranger & Copyist",
                # model="gpt-5",
                model="gpt-5-mini",
                instructions=system_prompt,
                model_settings={

                }
                # tools=[execute_code],
            )
            logger.info("Generating simplified MusicXML with OpenAI Agent...")
            attempts = int(os.getenv("OPENAI_RUN_ATTEMPTS", "2"))
            last_err = None
            for attempt in range(1, attempts + 1):
                try:
                    result = Runner.run_sync(starting_agent=code_execution_agent, input=query)
                    break
                except Exception as e:
                    last_err = e
                    if attempt < attempts:
                        backoff = 2 * attempt
                        logger.warning(f"Runner.run_sync failed (attempt {attempt}/{attempts}): {e}. Retrying in {backoff}s...")
                        time.sleep(backoff)
                    else:
                        raise
            print(result)
            result = result.final_output
        elif False:
            client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=timeout, max_retries=5)
            set_default_openai_client(client)
            logger.info("Generating simplified MusicXML with OpenAI Create...")
            response = client.responses.create(
                model="gpt-5",
                # model="gpt-5-mini",
                instructions=system_prompt,
                input=query,
            )
            result = response.output_text
            print(result)
        elif False:
            client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=timeout, max_retries=5)
            set_default_openai_client(client)
            logger.info("Generating simplified MusicXML with OpenAI Stream...")
            with client.responses.stream(
                model="gpt-5",
                # model="gpt-5-mini",
                instructions=system_prompt,
                input=query,
            ) as stream:
                for event in stream:
                    if event.type == "response.output_text.delta":
                        print(event.delta, end="", flush=True)
                result = stream.get_final_response()
                print(result)
        else:
            client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=timeout, max_retries=2)
            set_default_openai_client(client)
            logger.info("Generating simplified MusicXML with OpenAI Create with background=True...")
            start = client.responses.create(
                model="gpt-5",
                # model="gpt-5-mini",
                instructions=system_prompt,
                input=query,
                background=True,           # <-- long-running job
            )
            times_slept, minutes_to_sleep_in_seconds = 0, 60
            while True:
                r = client.responses.retrieve(start.id)
                if r.status == "completed":
                    result = r.output_text
                    break
                elif r.status in ("failed", "cancelled"):
                    raise RuntimeError(f"Job {r.status}. Result: {r}")
                logger.info(f"Job status: {r.status} (waiting {minutes_to_sleep_in_seconds}s). This can take up to 20 minutes (so far waited {times_slept}m)...")
                times_slept += 1
                time.sleep(minutes_to_sleep_in_seconds)

        # Parse the response to extract XML and optional filename from the two-section format
        full_output = (result or "").strip()

        # Try to extract the filename from the "===MUSICXML filename=\"...\"===" line
        filename_match = re.search(r'===MUSICXML\s+filename="([^"]+)"===', full_output)
        suggested_filename = filename_match.group(1) if filename_match else None

        # Extract the first XML code block
        xml_match = re.search(r"```xml\s*(.*?)\s*```", full_output, flags=re.DOTALL)
        if not xml_match:
            # Fallback: try any code fence
            xml_match = re.search(r"```\s*(.*?)\s*```", full_output, flags=re.DOTALL)
        if not xml_match:
            raise RuntimeError("Model response did not contain a MusicXML code block.")

        simplified_musicxml = xml_match.group(1).strip()

        # Save the simplified MusicXML to a new file
        if suggested_filename:
            output_path = p.with_name(suggested_filename)
        else:
            output_path = p.with_name(f"{p.stem}_simplified.musicxml")
        with open(output_path, "w") as f:
            f.write(simplified_musicxml)

        logger.info(f"✅ Simplified MusicXML saved to: {output_path}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

def generate_chatgpt_prompts_for_simplified_musicxml(musicxml_path: str) -> None:
    """
    Generates ChatGPT prompts for a given MusicXML file.
    """
    base_for_prompts = Path('src/piano_learning/resources')
    base_file_name = Path(musicxml_path).stem
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ctx = {"BASENAME": base_file_name, "TIMESTAMP": timestamp}

    print(render_template_file(base_for_prompts / 'system_instructions_for_chatgpt.j2', ctx))
    print('\n' + '='*80 + '\n')
    print(render_template_file(base_for_prompts / 'user_prompt_for_chatgpt.j2', ctx))
