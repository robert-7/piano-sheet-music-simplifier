from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.piano_learning.utils import simplification_plan

logger = logging.getLogger(__name__)


def get_measure_grid(musicxml_path: str | Path) -> list[dict[str, Any]]:
    """
    Return a compact measure grid for the LH planning prompt.
    """
    score = _parse_score(musicxml_path)
    return _measure_grid_from_score(score)


def _measure_grid_from_score(score: Any) -> list[dict[str, Any]]:
    """
    Return LH measure numbers and durations from an already parsed score.
    """
    part = _left_hand_part(score)
    grid: list[dict[str, Any]] = []
    current_time_signature = None

    for measure in part.getElementsByClass(_stream().Measure):
        if measure.timeSignature is not None:
            current_time_signature = measure.timeSignature
        time_signature = current_time_signature
        bar_duration = _measure_duration_ql(measure, time_signature)
        beat_count = float(getattr(time_signature, "beatCount", 1) or 1) if time_signature else 1.0
        grid.append(
            {
                "number": int(measure.number),
                "duration": bar_duration,
                "beatDuration": bar_duration / beat_count if beat_count else bar_duration,
            }
        )
    return grid


def get_measure_numbers(musicxml_path: str | Path) -> list[int]:
    """
    Return source measure numbers from the LH part.
    """
    return [entry["number"] for entry in get_measure_grid(musicxml_path)]


def write_simplified_musicxml_from_plan(
    musicxml_path: str | Path,
    plan: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """
    Apply a validated LH simplification plan to the source score and write MusicXML.
    """
    source_path = Path(musicxml_path)
    output_path = Path(output_path)
    score = _parse_score(source_path)
    measure_grid = _measure_grid_from_score(score)
    measure_numbers = [entry["number"] for entry in measure_grid]
    measure_durations_by_number = {entry["number"]: entry["duration"] for entry in measure_grid}
    normalized_plan = simplification_plan.validate_plan(
        plan,
        source_measure_numbers=measure_numbers,
        measure_durations_by_number=measure_durations_by_number,
        require_all_measures=True,
    )

    apply_plan_to_score(score, normalized_plan)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output_path = output_path.with_name(f".{output_path.stem}.tmp{output_path.suffix}")
    try:
        score.write("musicxml", fp=str(temporary_output_path))
        validate_musicxml_against_source(source_path, temporary_output_path)
        temporary_output_path.replace(output_path)
    except Exception:
        if temporary_output_path.exists():
            temporary_output_path.unlink()
        raise
    logger.info("Wrote plan-based simplified MusicXML to %s.", output_path)
    return output_path


def apply_plan_to_score(score: Any, plan: dict[str, Any]) -> Any:
    """
    Rewrite only the left-hand part in an already parsed music21 score.
    """
    part = _left_hand_part(score)
    measures_by_number = {int(measure.number): measure for measure in part.getElementsByClass(_stream().Measure)}

    for measure_plan in plan["measures"]:
        measure_number = measure_plan["number"]
        measure = measures_by_number.get(measure_number)
        if measure is None:
            raise ValueError(f"Cannot apply plan: measure {measure_number} was not found in LH part.")
        if measure_plan["texture"] == "preserve":
            continue

        _clear_musical_events(measure)
        for event in measure_plan["events"]:
            element = _event_to_music21_element(event)
            measure.insert(float(event["offset"]), element)

    return score


def validate_musicxml_against_source(source_path: str | Path, output_path: str | Path) -> None:
    """
    Validate that rewritten MusicXML parses and preserves source part/measure parity.
    """
    source_score = _parse_score(source_path)
    output_score = _parse_score(output_path)
    source_numbers_by_part = _measure_numbers_by_part(source_score)
    output_numbers_by_part = _measure_numbers_by_part(output_score)

    if len(source_numbers_by_part) != len(output_numbers_by_part):
        raise ValueError(
            f"Output part count {len(output_numbers_by_part)} does not match source part count "
            f"{len(source_numbers_by_part)}."
        )

    for index, source_numbers in enumerate(source_numbers_by_part):
        output_numbers = output_numbers_by_part[index]
        if output_numbers != source_numbers:
            raise ValueError(
                f"Output measure numbering for part {index + 1} does not match source. "
                f"Expected {source_numbers}; got {output_numbers}."
            )


def _parse_score(path: str | Path) -> Any:
    try:
        score = _converter().parse(str(path))
    except Exception as exc:
        raise ValueError(f"Failed to parse MusicXML score {path}: {exc}") from exc
    if not getattr(score, "parts", None):
        raise ValueError(f"MusicXML score {path} does not contain any parts.")
    return score


def _left_hand_part(score: Any) -> Any:
    if not score.parts:
        raise ValueError("Score does not contain any parts.")
    return score.parts[-1]


def _measure_numbers_by_part(score: Any) -> list[list[int]]:
    return [
        [int(measure.number) for measure in part.getElementsByClass(_stream().Measure)]
        for part in score.parts
    ]


def _measure_duration_ql(measure: Any, time_signature: Any | None) -> float:
    if time_signature is not None:
        try:
            return float(time_signature.barDuration.quarterLength)
        except Exception:
            pass
    highest_time = float(getattr(measure, "highestTime", 0.0) or 0.0)
    if highest_time > 0:
        return highest_time
    total = sum(float(getattr(element, "quarterLength", 0.0)) for element in measure.recurse().notesAndRests)
    return total if total > 0 else 4.0


def _clear_musical_events(measure: Any) -> None:
    stream_module = _stream()
    note_module = _note()
    chord_module = _chord()
    event_types = (stream_module.Voice, note_module.GeneralNote, chord_module.Chord)
    for element in list(measure):
        if not isinstance(element, event_types):
            continue
        try:
            measure.remove(element)
        except Exception:
            logger.debug("Could not remove element %r from measure %s.", element, measure.number)


def _event_to_music21_element(event: dict[str, Any]) -> Any:
    note_module = _note()
    chord_module = _chord()
    duration_module = _duration()

    if event["rest"]:
        element = note_module.Rest()
    elif len(event["pitches"]) == 1:
        element = note_module.Note(event["pitches"][0])
    else:
        element = chord_module.Chord(event["pitches"])

    element.duration = duration_module.Duration(float(event["duration"]))
    try:
        element.voice = "5"
    except Exception:
        pass
    return element


def _converter() -> Any:
    from music21 import converter

    return converter


def _stream() -> Any:
    from music21 import stream

    return stream


def _note() -> Any:
    from music21 import note

    return note


def _chord() -> Any:
    from music21 import chord

    return chord


def _duration() -> Any:
    from music21 import duration

    return duration
