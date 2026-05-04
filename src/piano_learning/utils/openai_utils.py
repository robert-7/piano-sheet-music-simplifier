import logging
import os
import time
from typing import Tuple

import dotenv
import httpx
import openai
from agents import Agent
from agents import Runner
from agents import set_default_openai_client

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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
OPENAI_AGENT_MODEL = os.getenv("OPENAI_AGENT_MODEL", "gpt-5.5")

def run_openai_response_in_background(
    api_key: str,
    timeout: httpx.Timeout,
    model: str,
    instructions: str,
    input_text: str,
    poll_interval_seconds: int = 60,
    max_retries: int = 2,
) -> Tuple[str, str]:
    """
    Create an OpenAI Responses job with background=True and poll until completion.

    Returns:
        (output_text, reasoning_summary)

    Raises:
        RuntimeError on unexpected status or terminal failure.
    """
    # TODO: Remove this. This is a workaround only for agents. The defaults work just fine in this scenario.
    client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=timeout, max_retries=max_retries)

    logger.info("Generating simplified MusicXML with OpenAI Create with background=True...")
    start = client.responses.create(
        model=model,
        instructions=instructions,
        input=input_text,
        background=True,
        # the standard output response consumes about 55k tokens (for a typical 2-page piece):
        # * the reasoning is about 12k token (on high effort with detailed summary level)
        # * the completion is about 43k tokens
        max_output_tokens=128000,
        # note: maxing out the reasoning effort to force the model to focus providing the most well-thought-out response
        # note: maxing out the reasoning summary to get the most detailed explanation of changes
        reasoning={"effort": "high", "summary": "detailed"},
    )

    times_slept = 0
    acceptable_statuses = {'completed', 'failed', 'in_progress', 'cancelled', 'queued', 'incomplete'}

    while True:
        r = client.responses.retrieve(start.id)
        status = r.status
        if status not in acceptable_statuses:
            raise RuntimeError(f"Unrecognized response status: {status}. Full response: {r}")
        if status in ("failed", "cancelled", "incomplete"):
            raise RuntimeError(f"Job {status}. Result: {r}")
        if status == "completed":
            logger.info("OpenAI Call status completed. Parsing output_text and reasoning...")
            try:
                output_text = r.output_text
            except Exception:
                output_text = ""
            try:
                reasoning_summary = r.reasoning.summary
            except Exception:
                reasoning_summary = ""
            return output_text, reasoning_summary

        emoji = "⏳" if status in ("queued",) else "🛠️"
        logger.info(f"{emoji} Pending job status: {status} (waiting {poll_interval_seconds}s). "
                    f"This can take up to 25 minutes (so far waited {times_slept}m)...")
        times_slept += 1
        time.sleep(poll_interval_seconds)

def run_openai_response_with_agent(
    api_key: str,
    timeout: httpx.Timeout,
    model: str,
    instructions: str,
    input_text: str,
    max_retries: int = 2,
) -> Tuple[str, str]:
    """
    NOTE: This function doesn't seem to work reliably yet. Use run_openai_response_in_background instead.
    Run an Agent (agents library) synchronously against the OpenAI API with basic retries.

    Behavior:
    - Creates a default OpenAI client and sets it for the agents runtime.
    - Builds an Agent with the provided model and instructions.
    - Executes Runner.run_sync with the given input, retrying with exponential backoff.
    - Returns the agent's final_output string.

    Note:
    - The number of attempts is read from the OPENAI_RUN_ATTEMPTS env var (default: 2).
    - max_retries applies to the underlying OpenAI client, not the agent attempts.

    Returns:
        final_output (str): The agent's final output text.

    Raises:
        Exception: The last exception if all attempts fail.
    """
    client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=timeout, max_retries=max_retries)
    set_default_openai_client(client)
    code_execution_agent = Agent(
        name="Expert Piano Arranger & Copyist",
        # TODO: GPT-5 isn't fully working with the agents library yet
        model=model,
        instructions=instructions,
        # TODO: Validate this. This parameter likely doesn't exist.
        # Set generous output tokens to ensure full MusicXML can be generated
        model_kwargs={"max_output_tokens": 16384, "response_format": {"type": "text"}},
    )
    logger.info("Generating simplified MusicXML with OpenAI Agent...")
    attempts = int(os.getenv("OPENAI_RUN_ATTEMPTS", "2"))
    for attempt in range(1, attempts + 1):
        try:
            result = Runner.run_sync(starting_agent=code_execution_agent, input=input_text)
            break
        except Exception as e:
            if attempt < attempts:
                backoff = 2 * attempt
                logger.warning(f"Runner.run_sync failed (attempt {attempt}/{attempts}): {e}. Retrying in {backoff}s...")
                time.sleep(backoff)
            else:
                raise
    result = result.final_output
