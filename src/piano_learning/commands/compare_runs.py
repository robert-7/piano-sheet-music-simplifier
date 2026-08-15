"""
Compare two simplification runs.

Issue #47's investigation workflow is "output the last two runs and see what
differs". This command loads the ``*_simplification_report.json`` from two run
directories (or files), diffs them, logs a short summary, and writes the diff to
``runs_comparison.json`` in the output directory.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.piano_learning.utils import simplification_report

logger = logging.getLogger(__name__)


def compare_runs(run_a: str | Path, run_b: str | Path, out_dir: str | Path) -> dict[str, Any]:
    """
    Load two run reports, diff them, persist the diff, and return it.

    ``run_a``/``run_b`` may be a report JSON file or a directory containing one.
    """
    report_a = simplification_report.load_report(run_a)
    report_b = simplification_report.load_report(run_b)
    diff = simplification_report.diff_reports(report_a, report_b)

    out_path = Path(out_dir) / "runs_comparison.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(diff, handle, ensure_ascii=False, indent=2)

    logger.info(
        "Run comparison: pctChanged %s vs %s; %d measures differ in texture. Wrote %s.",
        diff["pctChanged"]["a"],
        diff["pctChanged"]["b"],
        len(diff["divergentMeasures"]),
        out_path,
    )
    return diff
