import logging
import os
import time
from typing import Any
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


def get_openai_api_key() -> str:
    """
    Resolve the OpenAI API key only when an AI-backed simplification path is used.
    """
    return _get_required_env("OPENAI_API_KEY")


def _coerce_to_text(value: Any) -> str:
    """
    Best-effort conversion for SDK response objects that are not plain strings.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_coerce_to_text(item) for item in value if item is not None)
    try:
        text = getattr(value, "text")
        if isinstance(text, str):
            return text
    except Exception:
        pass
    return str(value)


def _build_openai_client(
    timeout: httpx.Timeout,
    max_retries: int,
    api_key: str | None = None,
) -> openai.OpenAI:
    return openai.OpenAI(
        api_key=api_key or get_openai_api_key(),
        timeout=timeout,
        max_retries=max_retries,
    )


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
OPENAI_AGENT_MODEL = os.getenv("OPENAI_AGENT_MODEL", "gpt-5.5")


def run_openai_response_in_background(
    timeout: httpx.Timeout,
    model: str,
    instructions: str,
    input_text: str,
    poll_interval_seconds: int = 60,
    max_retries: int = 2,
    api_key: str | None = None,
) -> Tuple[str, str]:
    """
    Create an OpenAI Responses job with background=True and poll until completion.

    Returns:
        (output_text, reasoning_summary)

    Raises:
        RuntimeError on unexpected status or terminal failure.
    """
    client = _build_openai_client(timeout=timeout, max_retries=max_retries, api_key=api_key)

    logger.info("Generating simplified MusicXML with OpenAI Responses API in background mode...")
    start = client.responses.create(
        model=model,
        instructions=instructions,
        input=input_text,
        background=True,
        # The current one-shot path can produce a large response; keep the cap generous until
        # the prompt/output contract is tightened in later issues.
        max_output_tokens=128000,
        reasoning={"effort": "high", "summary": "detailed"},
    )

    times_slept = 0
    acceptable_statuses = {"completed", "failed", "in_progress", "cancelled", "queued", "incomplete"}

    while True:
        response = client.responses.retrieve(start.id)
        status = response.status
        if status not in acceptable_statuses:
            raise RuntimeError(f"Unrecognized response status: {status}. Full response: {response}")
        if status in ("failed", "cancelled", "incomplete"):
            raise RuntimeError(f"Job {status}. Result: {response}")
        if status == "completed":
            logger.info("OpenAI call completed. Parsing output_text and reasoning...")
            try:
                output_text = response.output_text
            except Exception:
                output_text = ""
            try:
                reasoning_summary = _coerce_to_text(response.reasoning.summary)
            except Exception:
                reasoning_summary = ""
            return _coerce_to_text(output_text), reasoning_summary

        emoji = "⏳" if status in ("queued",) else "🛠️"
        logger.info(
            f"{emoji} Pending job status: {status} (waiting {poll_interval_seconds}s). "
            f"This can take up to 25 minutes (so far waited {times_slept}m)..."
        )
        times_slept += 1
        time.sleep(poll_interval_seconds)


def run_openai_response_with_agent(
    timeout: httpx.Timeout,
    model: str,
    instructions: str,
    input_text: str,
    max_retries: int = 2,
    api_key: str | None = None,
) -> Tuple[str, str]:
    """
    Run an Agent (agents library) synchronously against the OpenAI API with basic retries.

    NOTE:
    - This path remains experimental and is intentionally not the default.
    - max_retries applies to the underlying OpenAI client, not the agent attempts.

    Returns:
        (final_output_text, reasoning_summary)
    """
    logger.warning("OpenAI agent mode is experimental. Prefer the background Responses API path for normal runs.")
    client = _build_openai_client(timeout=timeout, max_retries=max_retries, api_key=api_key)
    set_default_openai_client(client)
    code_execution_agent = Agent(
        name="Expert Piano Arranger & Copyist",
        model=model,
        instructions=instructions,
    )
    logger.info("Generating simplified MusicXML with the OpenAI Agents SDK...")
    attempts = int(os.getenv("OPENAI_RUN_ATTEMPTS", "2"))
    result = None
    for attempt in range(1, attempts + 1):
        try:
            result = Runner.run_sync(starting_agent=code_execution_agent, input=input_text)
            break
        except Exception as exc:
            if attempt < attempts:
                backoff = 2 * attempt
                logger.warning(
                    f"Runner.run_sync failed (attempt {attempt}/{attempts}): {exc}. Retrying in {backoff}s..."
                )
                time.sleep(backoff)
            else:
                raise

    final_output = getattr(result, "final_output", "")
    return _coerce_to_text(final_output), ""
