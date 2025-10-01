import logging

from music21 import converter
from music21 import stream

logger = logging.getLogger(__name__)


def load_score(path: str) -> stream.Score:
    """Load a MusicXML score from the given path, raising if not found or invalid."""
    try:
        score = converter.parse(path)
        logger.info(f"Loaded score from '{path}' with {len(score.parts)} parts.")
        return score
    except Exception as e:
        raise Exception(f"Failed to load score from '{path}': {e}")
