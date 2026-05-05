from __future__ import annotations

import copy
import json
import re
from typing import Any

PLAN_SCHEMA_VERSION = "lh-simplification-plan/v1"
PLAN_SCOPE = "left-hand-only"
MIN_LH_DURATION_QL = 0.5
MAX_SIMULTANEOUS_LH_NOTES = 3
TIMING_EPSILON = 0.000001
ALLOWED_TEXTURES = {
    "block",
    "brokenArpeggio",
    "alberti",
    "singleBass",
    "dyad",
    "triad",
    "rest",
    "preserve",
}
TRUNCATION_MARKERS = (
    "TRUNCATED",
    "...",
    "[...continued",
    "[continued",
    "continued]",
)


def get_plan_schema() -> dict[str, Any]:
    """
    Return the JSON schema-like contract the model must follow.
    """
    return {
        "schemaVersion": PLAN_SCHEMA_VERSION,
        "scope": PLAN_SCOPE,
        "description": (
            "A left-hand-only simplification plan. The model outputs this JSON; local code "
            "rewrites MusicXML from it."
        ),
        "measureContract": {
            "number": "1-based source measure number.",
            "texture": sorted(ALLOWED_TEXTURES),
            "events": [
                {
                    "offset": "QuarterLength offset within the measure.",
                    "duration": "QuarterLength duration. Must be >= 0.5.",
                    "pitches": "0-3 music21 pitch names such as B-2, F#3, C4. Omit for rests.",
                    "rest": "Optional boolean. True means write a rest event.",
                }
            ],
            "timing": (
                "For non-preserve measures, events must cover the full source measure duration "
                "from offset 0 with no gaps or overlaps. Use explicit rest events for silence."
            ),
        },
        "requiredTopLevelKeys": ["schemaVersion", "scope", "measures"],
        "example": {
            "schemaVersion": PLAN_SCHEMA_VERSION,
            "scope": PLAN_SCOPE,
            "summary": "LH reduced to block dyads on strong beats.",
            "measures": [
                {
                    "number": 1,
                    "texture": "block",
                    "events": [
                        {"offset": 0.0, "duration": 1.0, "pitches": ["B-2", "F3"]},
                        {"offset": 1.0, "duration": 1.0, "pitches": ["B-3", "D4"]},
                        {"offset": 2.0, "duration": 1.0, "pitches": ["B-3", "F3"]},
                    ],
                }
            ],
        },
    }


def compact_analysis_for_plan(
    analysis: dict[str, Any],
    *,
    measure_grid: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Keep only analysis fields useful for LH planning.
    """
    compact: dict[str, Any] = {
        "metadata": analysis.get("metadata", {}),
        "measureGrid": measure_grid or [],
        "keys": analysis.get("keys", []),
        "harmonies": analysis.get("harmonies", []),
        "textureLH": analysis.get("textureLH", []),
        "ranges": {"LH": analysis.get("ranges", {}).get("LH")},
        "cadences": analysis.get("cadences", []),
    }
    return {key: value for key, value in compact.items() if value not in ({}, [], {"LH": None})}


def extract_plan_json(output_text: str) -> dict[str, Any]:
    """
    Extract a plan JSON object from model output.
    """
    if not output_text.strip():
        raise ValueError("Model response is empty; expected a simplification-plan JSON object.")
    _reject_truncation_markers(output_text)

    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", output_text, flags=re.DOTALL | re.IGNORECASE)
    candidate = fenced_match.group(1).strip() if fenced_match else output_text.strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        start = candidate.find("{")
        if start == -1:
            raise ValueError("Model response did not contain a JSON object.") from None
        try:
            parsed, _ = decoder.raw_decode(candidate[start:])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model response did not contain valid plan JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Simplification plan must be a JSON object.")
    return parsed


def validate_plan(
    plan: dict[str, Any],
    *,
    source_measure_numbers: list[int] | None = None,
    measure_durations_by_number: dict[int, float] | None = None,
    require_all_measures: bool = True,
    require_full_measure_coverage: bool = True,
) -> dict[str, Any]:
    """
    Validate and normalize a left-hand simplification plan.
    """
    if not isinstance(plan, dict):
        raise ValueError("Simplification plan must be a dictionary.")

    schema_version = plan.get("schemaVersion")
    if schema_version != PLAN_SCHEMA_VERSION:
        raise ValueError(f"Unsupported schemaVersion={schema_version!r}; expected {PLAN_SCHEMA_VERSION!r}.")

    scope = plan.get("scope")
    if scope != PLAN_SCOPE:
        raise ValueError(f"Unsupported scope={scope!r}; expected {PLAN_SCOPE!r}.")

    measures = plan.get("measures")
    if not isinstance(measures, list) or not measures:
        raise ValueError("Simplification plan must contain a non-empty measures list.")

    normalized_measures: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    for measure in measures:
        normalized_measure = _validate_measure(measure)
        number = normalized_measure["number"]
        if number in seen_numbers:
            raise ValueError(f"Duplicate plan entry for measure {number}.")
        seen_numbers.add(number)
        normalized_measures.append(normalized_measure)

    if source_measure_numbers is not None:
        expected = set(source_measure_numbers)
        missing = sorted(expected - seen_numbers)
        extra = sorted(seen_numbers - expected)
        if require_all_measures and missing:
            raise ValueError(f"Simplification plan is missing source measures: {missing}.")
        if extra:
            raise ValueError(f"Simplification plan references non-source measures: {extra}.")

    if measure_durations_by_number is not None:
        for measure in normalized_measures:
            duration = measure_durations_by_number.get(measure["number"])
            if duration is not None:
                _validate_measure_timing(
                    measure,
                    measure_duration=float(duration),
                    require_full_measure_coverage=require_full_measure_coverage,
                )

    normalized = copy.deepcopy(plan)
    normalized["schemaVersion"] = PLAN_SCHEMA_VERSION
    normalized["scope"] = PLAN_SCOPE
    normalized["measures"] = sorted(normalized_measures, key=lambda item: item["number"])
    return normalized


def _validate_measure(measure: Any) -> dict[str, Any]:
    if not isinstance(measure, dict):
        raise ValueError("Each measure plan entry must be a dictionary.")

    number = measure.get("number", measure.get("measure"))
    if not isinstance(number, int) or number <= 0:
        raise ValueError(f"Invalid measure number: {number!r}.")

    texture = measure.get("texture")
    if texture not in ALLOWED_TEXTURES:
        raise ValueError(f"Measure {number} uses unsupported texture={texture!r}.")

    events = measure.get("events", [])
    if not isinstance(events, list):
        raise ValueError(f"Measure {number} events must be a list.")
    if texture == "preserve" and events:
        raise ValueError(f"Measure {number} uses texture='preserve' and must not include replacement events.")
    if texture != "preserve" and not events:
        raise ValueError(f"Measure {number} must include at least one event.")

    normalized_events = [_validate_event(number, event) for event in events]
    return {
        "number": number,
        "texture": texture,
        "events": sorted(normalized_events, key=lambda item: item["offset"]),
    }


def _validate_event(measure_number: int, event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError(f"Measure {measure_number} contains a non-object event.")

    offset = _coerce_number(event.get("offset"), f"measure {measure_number} event offset")
    duration = _coerce_number(event.get("duration"), f"measure {measure_number} event duration")
    if offset < 0:
        raise ValueError(f"Measure {measure_number} event offset cannot be negative.")
    if duration < MIN_LH_DURATION_QL:
        raise ValueError(
            f"Measure {measure_number} event duration {duration} is shorter than an eighth note "
            f"({MIN_LH_DURATION_QL} quarterLength)."
        )

    rest = bool(event.get("rest", False))
    pitches = event.get("pitches", [])
    if pitches is None:
        pitches = []
    if not isinstance(pitches, list):
        raise ValueError(f"Measure {measure_number} event pitches must be a list.")
    if len(pitches) > MAX_SIMULTANEOUS_LH_NOTES:
        raise ValueError(f"Measure {measure_number} event has more than {MAX_SIMULTANEOUS_LH_NOTES} pitches.")
    if not rest and not pitches:
        raise ValueError(f"Measure {measure_number} event must include pitches or rest=true.")
    if rest and pitches:
        raise ValueError(f"Measure {measure_number} rest event cannot also include pitches.")
    for pitch in pitches:
        if not isinstance(pitch, str) or not pitch.strip():
            raise ValueError(f"Measure {measure_number} event contains an invalid pitch: {pitch!r}.")

    return {
        "offset": float(offset),
        "duration": float(duration),
        "rest": rest,
        "pitches": [pitch.strip() for pitch in pitches],
    }


def _coerce_number(value: Any, field_name: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"Invalid {field_name}: {value!r}.")


def _validate_measure_timing(
    measure: dict[str, Any],
    *,
    measure_duration: float,
    require_full_measure_coverage: bool,
) -> None:
    number = measure["number"]
    if measure_duration <= 0:
        raise ValueError(f"Measure {number} has invalid source duration {measure_duration}.")
    if measure["texture"] == "preserve":
        return

    previous_end = 0.0
    for event in measure["events"]:
        offset = event["offset"]
        duration = event["duration"]
        event_end = offset + duration
        if event_end > measure_duration + TIMING_EPSILON:
            raise ValueError(
                f"Measure {number} event ending at {event_end} exceeds source duration {measure_duration}."
            )
        if offset < previous_end - TIMING_EPSILON:
            raise ValueError(f"Measure {number} contains overlapping events at offset {offset}.")
        if require_full_measure_coverage and abs(offset - previous_end) > TIMING_EPSILON:
            raise ValueError(
                f"Measure {number} contains a timing gap before offset {offset}; use an explicit rest event."
            )
        previous_end = event_end

    if require_full_measure_coverage and abs(previous_end - measure_duration) > TIMING_EPSILON:
        raise ValueError(
            f"Measure {number} does not cover the full source duration {measure_duration}; "
            "use explicit rest events for silence."
        )


def _reject_truncation_markers(text: str) -> None:
    upper_text = text.upper()
    for marker in TRUNCATION_MARKERS:
        if marker.upper() in upper_text:
            raise ValueError(f"Model response contains truncation marker {marker!r}.")
