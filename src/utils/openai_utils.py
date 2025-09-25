import logging
import time
from typing import Tuple

import httpx
import openai

logger = logging.getLogger(__name__)

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
    client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)

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
