"""
Run artifacts: one place that owns the *names, layout, and summary* of the files
a simplification run leaves behind.

Before this module the OpenAI backend spelled artifact names inline with
inconsistent prefixes, and a failed run could vanish without a trail. Centralizing
the naming here means:

- names are consistent (``<stem>_<role>.<ext>``, flat in the run's output dir),
- load-bearing names (consumed by ``run_e2e.sh`` and ``compare_runs``) can't drift
  silently -- they are pinned in :data:`ARTIFACT_SPECS` and covered by tests,
- every run can emit a single :data:`RUN_SUMMARY_FILENAME` describing what was
  sent, what came back, what failed validation, and what was finally written.

See ``docs/DEBUGGING.md`` for the human-facing artifact map.

The functions here are deliberately pure/IO-light so the naming and summary logic
can be unit-tested without music21 or the OpenAI SDK.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
RUN_SUMMARY_FILENAME = "run_summary.json"

# Artifact role -> (filename suffix, extension). A file is ``<stem>_<suffix>.<ext>``.
# Roles are grouped by the debugging question they answer. The final-output roles
# are LOAD-BEARING: their names are consumed by external tooling (``run_e2e.sh``
# checks ``<stem>_simplified.musicxml`` / ``<stem>_analysis.json``; ``compare_runs``
# globs ``*_simplification_report.json``). Do not rename them without updating
# those consumers -- the tests in ``test_run_artifacts.py`` guard against drift.
ARTIFACT_SPECS: dict[str, tuple[str, str]] = {
    # Prompt inputs -- what was sent to the model.
    "prompt_system": ("prompt_system", "txt"),
    "prompt_user": ("prompt_user", "txt"),
    "prompt_compact_analysis": ("prompt_compact_analysis", "json"),
    "prompt_plan_schema": ("prompt_plan_schema", "json"),
    # Model output -- what came back, raw, before any validation.
    "model_output_raw": ("model_output_raw", "txt"),
    "model_reasoning": ("model_reasoning", "txt"),
    # Structured plan -- the extracted, validated LH plan.
    "plan": ("simplification_plan", "json"),
    # Validation -- pass/fail outcome of validating the plan.
    "validation_report": ("validation_report", "json"),
    # Final outputs -- LOAD-BEARING names (see note above).
    "analysis": ("analysis", "json"),
    "simplified_musicxml": ("simplified", "musicxml"),
    "simplification_report": ("simplification_report", "json"),
}

# Reserved for the targeted-repair flow (#70), which is not implemented yet. The
# name is fixed here so repair attempts slot into the same flat layout without a
# future rename. See :func:`repair_attempt_filename`.
REPAIR_ATTEMPT_PREFIX = "repair_attempt"


def artifact_filename(stem: str, role: str) -> str:
    """Return the flat filename for ``role`` under a run whose input stem is ``stem``."""
    try:
        suffix, extension = ARTIFACT_SPECS[role]
    except KeyError as exc:
        raise KeyError(
            f"Unknown artifact role: {role!r}. Known roles: {sorted(ARTIFACT_SPECS)}"
        ) from exc
    return f"{stem}_{suffix}.{extension}"


def artifact_path(out_dir: str | Path, stem: str, role: str) -> Path:
    """Return the full path for ``role`` inside ``out_dir``."""
    return Path(out_dir) / artifact_filename(stem, role)


def repair_attempt_filename(stem: str, attempt: int) -> str:
    """
    Reserved name for a repair attempt's plan (targeted-repair flow, #70).

    Not written by any current code path; documented and tested so the future
    flow uses a name consistent with the rest of the layout.
    """
    return f"{stem}_{REPAIR_ATTEMPT_PREFIX}_{attempt:02d}.json"


def _coerce_to_text(value: Any) -> str:
    """Best-effort text for artifact bodies that are not dict/list/str."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def write_artifact(out_dir: str | Path, stem: str, role: str, data: Any) -> Path:
    """
    Write ``data`` for ``role`` into ``out_dir`` and log where it went.

    dict/list payloads are written as pretty JSON; anything else is coerced to
    text. Returns the path written.
    """
    path = artifact_path(out_dir, stem, role)
    with open(path, "w", encoding="utf-8") as handle:
        if isinstance(data, (dict, list)):
            handle.write(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            handle.write(_coerce_to_text(data))
    logger.info("✅ %s saved to: %s", role, path)
    return path


def report_highlights_from_report(report: dict[str, Any]) -> dict[str, Any]:
    """
    Pull the at-a-glance fields out of a full simplification report for the run
    summary (the per-measure detail stays in ``*_simplification_report.json``).
    """
    return {
        "measuresTotal": report.get("measuresTotal"),
        "measuresChanged": report.get("measuresChanged"),
        "pctChanged": report.get("pctChanged"),
        "lhNoteDelta": report.get("lhNoteCountDelta", {}).get("delta"),
        "unmodifiedFlag": report.get("unmodifiedFlag"),
    }


def build_run_summary(
    *,
    input_source: str,
    input_path: str,
    stem: str,
    simplifier: str,
    outcome: str,
    out_dir: str | Path,
    mode: str | None = None,
    model: str | None = None,
    request: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    report_highlights: dict[str, Any] | None = None,
    error: str | None = None,
    artifact_roles: list[str] | None = None,
) -> dict[str, Any]:
    """
    Assemble the per-run summary describing what a run did.

    Pure: the ``artifacts`` map reflects what actually exists on disk in
    ``out_dir`` at call time (so a failed run honestly shows the plan/output
    missing), but nothing is written here -- use :func:`write_run_summary`.

    Fields that only apply to the OpenAI path (``request``, ``validation``) are
    omitted entirely when not provided, rather than left as ``None`` noise.
    """
    out_dir_path = Path(out_dir)
    artifacts = [
        {
            "role": role,
            "file": artifact_filename(stem, role),
            "exists": (out_dir_path / artifact_filename(stem, role)).exists(),
        }
        for role in (artifact_roles or [])
    ]

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "input": {"source": input_source, "path": input_path, "stem": stem},
        "simplifier": simplifier,
        "mode": mode,
        "model": model,
        "outcome": outcome,
        "error": error,
        "reportHighlights": report_highlights,
        "artifacts": artifacts,
    }
    if request is not None:
        summary["request"] = request
    if validation is not None:
        summary["validation"] = validation
    return summary


def summary_log_line(summary: dict[str, Any]) -> str:
    """One-line human summary of a run, suitable for an INFO log line."""
    parts = [
        f"Run {summary.get('outcome')}",
        f"backend={summary.get('simplifier')}",
    ]
    if summary.get("mode"):
        parts.append(f"mode={summary['mode']}")
    if summary.get("model"):
        parts.append(f"model={summary['model']}")
    highlights = summary.get("reportHighlights") or {}
    if highlights.get("pctChanged") is not None:
        parts.append(f"pctChanged={highlights['pctChanged']}")
    if highlights.get("unmodifiedFlag"):
        parts.append("UNMODIFIED")
    if summary.get("error"):
        parts.append(f"error={summary['error']}")
    return "; ".join(parts)


def write_run_summary(out_dir: str | Path, summary: dict[str, Any]) -> Path:
    """Write ``summary`` to ``<out_dir>/run_summary.json`` and log a one-liner."""
    path = Path(out_dir) / RUN_SUMMARY_FILENAME
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    logger.info("📝 Run summary (%s): %s", path, summary_log_line(summary))
    return path
