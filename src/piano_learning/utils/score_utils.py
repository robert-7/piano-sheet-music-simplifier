import logging

from music21 import converter
from music21 import stream

logger = logging.getLogger(__name__)


def load_score(path: str) -> stream.Score:
    """Load a MusicXML score from the given path, raising if not found or invalid."""
    try:
        parsed = converter.parse(path)
    except Exception as e:
        raise Exception(f"Failed to load score from '{path}': {e}")
    # converter.parse may return a Score, Part, or Opus; this loader contracts
    # to a Score, so narrow explicitly and fail loudly on anything else.
    if not isinstance(parsed, stream.Score):
        raise TypeError(
            f"Expected a Score from '{path}', got {type(parsed).__name__}."
        )
    logger.info(f"Loaded score from '{path}' with {len(parsed.parts)} parts.")
    return parsed
