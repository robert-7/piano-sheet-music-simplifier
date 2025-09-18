import logging
import os
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

        # Set up the OpenAI client
        timeout = httpx.Timeout(300.0, read=300.0, write=60.0, connect=30.0)
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=timeout, max_retries=3)
        set_default_openai_client(client)
        code_execution_agent = Agent(
            name="Music Theorist and Composer Agent",
            # avoid gpt-5 for now with agents: https://github.com/openai/openai-agents-python/issues/1397
            model="gpt-4.1",
            instructions=(f"""
                You are an expert music theorist and composer.
                Your task is to create a simplified arrangement of the provided MusicXML file.
                The goal is to reduce the technical complexity of the accompaniment while keeping the piece the same length.
                Preserve the full right-hand melody exactly as written, and keep the harmonic structure intact.
                Simplify the left-hand part by replacing broken arpeggios or complex patterns with simpler arpeggios, blocked chords or basic chordal accompaniment.
                The result should be a beginner-friendly piano arrangement that maintains the original character of the piece without shortening or omitting sections.

                Additionally, you may also receive a harmony analysis of the piece.
                You may use the analysis of the MusicXML or provide your own, more thorough analysis.

                Only return the raw, simplified MusicXML content, with no explanations or pleasantries.
                """
            ),
            # tools=[execute_code],
        )

        logger.info("Generating simplified MusicXML with OpenAI...")
        query = (f"""Here is my musicxml file:
            ```xml
            {musicxml_content}
            ```
            Please simplify it based on the following analysis (or provide your own analysis if this is insufficient):
            ```plaintext
            {analysis}
            ```
            """
        )
        result = Runner.run_sync(starting_agent=code_execution_agent, input=query)
        print(result)

        # Clean the response to get only the XML
        simplified_musicxml = (result.final_output or "").strip()
        if "```xml" in simplified_musicxml:
            simplified_musicxml = simplified_musicxml.split("```xml")[1].split("```")[0].strip()

        # Save the simplified MusicXML to a new file
        p = Path(musicxml_path)
        output_path = p.with_name(f"{p.stem}_simplified.musicxml")
        with open(output_path, "w") as f:
            f.write(simplified_musicxml)

        logger.info(f"✅ Simplified MusicXML saved to: {output_path}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
