import logging
import os
import re
from datetime import datetime
from pathlib import Path

import dotenv
import httpx
from agents import Agent
from agents import function_tool
from agents import Runner
from agents import set_default_openai_client
from openai import AsyncOpenAI

from src.commands.generate_legacy_analysis_of_musicxml import analyze_harmony
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

def generate_simplified_musicxml(musicxml_path: str) -> None:
    """
    Generates a simplified version of a MusicXML file using an AI agent.
    """
    try:
        score = score_utils.load_score(musicxml_path)
        analysis = analyze_harmony(score)
        with open(musicxml_path) as f:
            musicxml_content = f.read()

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
        timeout = httpx.Timeout(300.0, read=300.0, write=60.0, connect=30.0)
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=timeout, max_retries=3)
        set_default_openai_client(client)
        code_execution_agent = Agent(
            name="Music Theorist and Composer Agent",
            # avoid gpt-5 for now with agents: https://github.com/openai/openai-agents-python/issues/1397
            model="gpt-4.1",
            instructions=system_prompt,
            # tools=[execute_code],
        )

        logger.info("Generating simplified MusicXML with OpenAI...")
        query = (
            f"{user_prompt}\n\n"
            "Here is the MusicXML content (inline attachment):\n"
            "```xml\n"
            f"{musicxml_content}\n"
            "```\n\n"
            "Here is the harmony analysis JSON (inline attachment):\n"
            "```json\n"
            f"{analysis}\n"
            "```\n"
        )
        result = Runner.run_sync(starting_agent=code_execution_agent, input=query)
        print(result)

        # Parse the response to extract XML and optional filename from the two-section format
        full_output = (result.final_output or "").strip()

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
