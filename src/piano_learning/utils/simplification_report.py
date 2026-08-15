"""
Simplification reporting.

Issue #47 asks us to *see* why the pipeline sometimes returns nearly unmodified
sheet music. This module turns a source score plus a simplification outcome (an
LH plan from the OpenAI backend, or a rewritten score from the music21 backend)
into a compact, machine- and human-readable report:

- How many measures actually changed vs. were left as-is (``preserve``).
- A histogram of the chosen LH textures.
- The left-hand note-count delta (negative means the LH got simpler).
- An ``unmodifiedFlag`` so a "nothing really happened" run is loud, not silent.
- When prescriptive recommendations are available, how often the plan followed
  vs. overrode them.

The aggregation logic (:func:`summarize_measures`) is deliberately pure so it can
be unit-tested without music21; only the ``build_*`` helpers parse scores.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PRESERVE_TEXTURE = "preserve"
REPORT_FILENAME_SUFFIX = "_simplification_report.json"
# A run whose changed-measure share is at or below this percentage is flagged as
# "nearly unmodified" so the failure is visible in logs and the report.
UNMODIFIED_PCT_THRESHOLD = 10.0


def summarize_measures(per_measure: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Aggregate per-measure planning outcomes into a simplification report.

    Pure function (no music21, no IO) so the reporting logic is independently
    testable. Each ``per_measure`` entry is expected to carry at least
    ``number``, ``changed``, ``planTexture``, ``sourceNoteCount`` and
    ``planNoteCount``; ``recommendationFollowed`` is optional.
    """
    total = len(per_measure)
    changed = sum(1 for entry in per_measure if entry.get("changed"))
    preserved = total - changed
    pct_changed = round((changed / total) * 100, 2) if total else 0.0

    histogram: dict[str, int] = {}
    for entry in per_measure:
        texture = entry.get("planTexture") or "unknown"
        histogram[texture] = histogram.get(texture, 0) + 1

    source_notes = sum(int(entry.get("sourceNoteCount", 0)) for entry in per_measure)
    plan_notes = sum(int(entry.get("planNoteCount", 0)) for entry in per_measure)

    followed = sum(1 for entry in per_measure if entry.get("recommendationFollowed") is True)
    overridden = sum(1 for entry in per_measure if entry.get("recommendationFollowed") is False)

    report: dict[str, Any] = {
        "measuresTotal": total,
        "measuresPreserved": preserved,
        "measuresChanged": changed,
        "pctChanged": pct_changed,
        "unmodifiedFlag": total > 0 and pct_changed <= UNMODIFIED_PCT_THRESHOLD,
        "textureHistogram": histogram,
        "lhNoteCountDelta": {
            "source": source_notes,
            "plan": plan_notes,
            "delta": plan_notes - source_notes,
        },
        "perMeasure": per_measure,
    }
    if followed or overridden:
        report["recommendationsFollowed"] = followed
        report["recommendationsOverridden"] = overridden
    return report


def summary_line(report: dict[str, Any]) -> str:
    """
    One-line human summary of a report, suitable for logging.
    """
    delta = report.get("lhNoteCountDelta", {}).get("delta")
    line = (
        f"{report['measuresChanged']}/{report['measuresTotal']} measures changed "
        f"({report['pctChanged']}%); LH note delta {delta}"
    )
    if "recommendationsOverridden" in report:
        line += (
            f"; {report['recommendationsFollowed']} recommendations followed, "
            f"{report['recommendationsOverridden']} overridden"
        )
    return line


def build_simplification_report(
    source_musicxml_path: str | Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a report by comparing a validated LH plan against the source score.

    Used by the OpenAI backend, whose ``plan`` carries the per-measure texture
    decisions (including ``preserve``) that drive the "unmodified" outcome.
    """
    # Imported lazily so this module stays importable (and partly testable)
    # without music21 installed.
    from src.piano_learning.commands import generate_analysis_of_musicxml
    from src.piano_learning.utils import score_utils

    score = score_utils.load_score(str(source_musicxml_path))
    source_note_counts = _lh_note_counts_by_measure(score)
    source_textures = _source_textures_by_measure(generate_analysis_of_musicxml.classify_lh_texture(score))
    recommendations = {
        recommendation.number: recommendation
        for recommendation in generate_analysis_of_musicxml.build_prescriptive_analysis(score)
    }

    per_measure: list[dict[str, Any]] = []
    for measure_plan in plan.get("measures", []):
        number = int(measure_plan["number"])
        texture = measure_plan.get("texture")
        changed = texture != PRESERVE_TEXTURE
        source_count = source_note_counts.get(number, 0)
        plan_count = _plan_note_count(measure_plan) if changed else source_count

        entry: dict[str, Any] = {
            "number": number,
            "sourceTexture": source_textures.get(number),
            "planTexture": texture,
            "changed": changed,
            "sourceNoteCount": source_count,
            "planNoteCount": plan_count,
        }
        recommendation = recommendations.get(number)
        if recommendation is not None:
            entry["recommendation"] = recommendation.targetTexture
            entry["recommendationFollowed"] = texture == recommendation.targetTexture
        per_measure.append(entry)

    per_measure.sort(key=lambda item: item["number"])
    return summarize_measures(per_measure)


def build_music21_report(
    source_musicxml_path: str | Path,
    simplified_musicxml_path: str | Path,
) -> dict[str, Any]:
    """
    Build a report for the deterministic music21 backend by comparing the
    source and rewritten scores directly (there is no plan object here).
    """
    from src.piano_learning.commands import generate_analysis_of_musicxml
    from src.piano_learning.utils import score_utils

    source_score = score_utils.load_score(str(source_musicxml_path))
    simplified_score = score_utils.load_score(str(simplified_musicxml_path))
    source_counts = _lh_note_counts_by_measure(source_score)
    simplified_counts = _lh_note_counts_by_measure(simplified_score)
    source_events = _lh_note_events_by_measure(source_score)
    simplified_events = _lh_note_events_by_measure(simplified_score)
    source_textures = _source_textures_by_measure(generate_analysis_of_musicxml.classify_lh_texture(source_score))

    per_measure: list[dict[str, Any]] = []
    for number in sorted(source_counts):
        source_count = source_counts[number]
        plan_count = simplified_counts.get(number, source_count)
        # Compare actual note/chord content, not just counts: a reduction can
        # rearrange a busy figure into fewer, denser events that happen to sum
        # to the same note count (e.g. an eighth-note Alberti bar collapsed
        # into same-count block chords), which count equality would miss.
        changed = simplified_events.get(number, ()) != source_events.get(number, ())
        per_measure.append(
            {
                "number": number,
                "sourceTexture": source_textures.get(number),
                # The music21 reducer emits block chords; label unchanged bars as preserve.
                "planTexture": "block" if changed else PRESERVE_TEXTURE,
                "changed": changed,
                "sourceNoteCount": source_count,
                "planNoteCount": plan_count,
            }
        )
    return summarize_measures(per_measure)


def diff_reports(report_a: dict[str, Any], report_b: dict[str, Any]) -> dict[str, Any]:
    """
    Compare two reports (e.g. two runs of the same piece) and surface where they
    diverge. This operationalizes issue #47's "output the last two runs and see
    what differs" step.
    """
    per_a = {entry["number"]: entry for entry in report_a.get("perMeasure", [])}
    per_b = {entry["number"]: entry for entry in report_b.get("perMeasure", [])}

    divergent: list[dict[str, Any]] = []
    for number in sorted(set(per_a) | set(per_b)):
        texture_a = per_a.get(number, {}).get("planTexture")
        texture_b = per_b.get(number, {}).get("planTexture")
        if texture_a != texture_b:
            divergent.append({"number": number, "a": texture_a, "b": texture_b})

    return {
        "pctChanged": {"a": report_a.get("pctChanged"), "b": report_b.get("pctChanged")},
        "measuresChanged": {"a": report_a.get("measuresChanged"), "b": report_b.get("measuresChanged")},
        "lhNoteDelta": {
            "a": report_a.get("lhNoteCountDelta", {}).get("delta"),
            "b": report_b.get("lhNoteCountDelta", {}).get("delta"),
        },
        "divergentMeasures": divergent,
    }


def write_report(report: dict[str, Any], out_dir: str | Path, basename: str) -> Path:
    """
    Write a report to ``<out_dir>/<basename>_simplification_report.json``.
    """
    out_path = Path(out_dir) / f"{basename}{REPORT_FILENAME_SUFFIX}"
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    logger.info("Wrote simplification report to %s.", out_path)
    return out_path


def load_report(path: str | Path) -> dict[str, Any]:
    """
    Load a report JSON. If ``path`` is a directory, the first
    ``*_simplification_report.json`` inside it is used.
    """
    resolved = Path(path)
    if resolved.is_dir():
        matches = sorted(resolved.glob(f"*{REPORT_FILENAME_SUFFIX}"))
        if not matches:
            raise FileNotFoundError(f"No simplification report found in directory: {resolved}")
        resolved = matches[0]
    return json.loads(resolved.read_text(encoding="utf-8"))


def _plan_note_count(measure_plan: dict[str, Any]) -> int:
    """Count sounding LH pitches in a plan measure (rests contribute nothing)."""
    total = 0
    for event in measure_plan.get("events", []):
        if event.get("rest"):
            continue
        total += len(event.get("pitches", []))
    return total


def _lh_note_counts_by_measure(score: Any) -> dict[int, int]:
    """Count sounding LH pitches per measure, expanding chords into their pitches."""
    from music21 import chord as m21chord
    from music21 import stream as m21stream

    if not getattr(score, "parts", None):
        return {}
    left_hand = score.parts[-1]
    counts: dict[int, int] = {}
    for measure in left_hand.getElementsByClass(m21stream.Measure):
        count = 0
        for element in measure.flatten().notes:
            if isinstance(element, m21chord.Chord):
                count += len(element.pitches)
            else:
                count += 1
        counts[int(measure.number)] = count
    return counts


def _lh_note_events_by_measure(score: Any) -> dict[int, tuple[tuple[float, float, tuple[int, ...]], ...]]:
    """
    Per-measure signature of the LH's sounding content: for each note/chord,
    ``(offset, duration, sorted MIDI pitches)``.

    Used instead of a raw note count to detect whether a measure's LH actually
    changed: a reduction can rearrange notes into the same total count (e.g. an
    eighth-note figure collapsed into same-count block chords), which count
    equality alone would miss.
    """
    from music21 import chord as m21chord
    from music21 import stream as m21stream

    if not getattr(score, "parts", None):
        return {}
    left_hand = score.parts[-1]
    events_by_measure: dict[int, tuple[tuple[float, float, tuple[int, ...]], ...]] = {}
    for measure in left_hand.getElementsByClass(m21stream.Measure):
        events: list[tuple[float, float, tuple[int, ...]]] = []
        for element in measure.flatten().notes:
            pitches = (
                tuple(sorted(p.midi for p in element.pitches))
                if isinstance(element, m21chord.Chord)
                else (element.pitch.midi,)
            )
            events.append((round(float(element.offset), 3), round(float(element.duration.quarterLength), 3), pitches))
        events_by_measure[int(measure.number)] = tuple(events)
    return events_by_measure


def _source_textures_by_measure(spans: list[Any]) -> dict[int, str]:
    """Expand merged texture spans into a per-measure texture lookup."""
    textures: dict[int, str] = {}
    for span in spans:
        start, end = span.mRange
        for number in range(int(start), int(end) + 1):
            textures[number] = span.pattern
    return textures
