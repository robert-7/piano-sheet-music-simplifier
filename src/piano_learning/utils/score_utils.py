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


def dissolve_voices(score: stream.Score) -> None:
    """Merge every measure's voices back into the measure in place, dropping the voice containers.

    Works around a music21 export crash on OMR output. Audiveris frequently emits measures whose
    voice contents overshoot the barline (it warns "No target duration ... check time signatures"),
    and it reuses a given voice id in only some measures. On export music21's ``makeRests`` gives
    each such voice an over-long rest and ``makeTies`` then tries to bridge it into the *next*
    measure's same-id voice via ``mNext.voices[vId]`` -- which raises ``KeyError`` when that measure
    has voices but not that id (see makeNotation.py). Flattening voices removes the id-matching step
    entirely; music21 re-derives consistent voices from the notes on export. All notes/rests are
    preserved at their absolute measure offsets, so pitches and durations are unchanged.
    """
    for measure in list(score.recurse().getElementsByClass(stream.Measure)):
        for voice in list(measure.voices):
            for element in list(voice):
                offset = voice.elementOffset(element)
                voice.remove(element)
                measure.insert(offset, element)
            measure.remove(voice)
