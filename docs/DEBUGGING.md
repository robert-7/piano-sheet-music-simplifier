# Debugging artifacts

Every simplification run writes a standardized set of files into its output
directory (`user/output/TIMESTAMP/`, or wherever `--out-dir` points). This page
is the map: what each file is, which debugging question it answers, and which
backend produces it. Naming and layout are owned by
[`src/piano_learning/utils/run_artifacts.py`](../src/piano_learning/utils/run_artifacts.py)
so the names stay consistent and cannot drift silently.

Inputs are never modified. Artifacts are flat inside the run directory and are
prefixed with the input file's stem (e.g. `Kakariko_Village_...`); the run-level
`run_summary.json` and `piano_learning.log` are the exceptions.

## The artifact map

`<stem>` is the input file's base name (`Kakariko_Village` for
`Kakariko_Village.musicxml`).

| Category | File | What it answers | Backend |
| --- | --- | --- | --- |
| Prompt inputs | `<stem>_prompt_system.txt` | The system instructions sent to the model | openai |
| Prompt inputs | `<stem>_prompt_user.txt` | The full user prompt (schema + compact analysis) sent to the model | openai |
| Prompt inputs | `<stem>_prompt_compact_analysis.json` | The compact analysis the model was asked to plan from | openai |
| Prompt inputs | `<stem>_prompt_plan_schema.json` | The plan JSON schema the output must validate against | openai |
| Model output | `<stem>_model_output_raw.txt` | Exactly what the model returned, before any parsing | openai |
| Model output | `<stem>_model_reasoning.txt` | The model's reasoning summary, when available | openai |
| Validation | `<stem>_validation_report.json` | Whether the plan passed validation, and the error if not | openai |
| Structured plan | `<stem>_simplification_plan.json` | The extracted, validated LH plan that drove the rewrite | openai |
| Final output | `<stem>_analysis.json` | The harmony analysis of the source score | both\* |
| Final output | `<stem>_simplified.musicxml` | The simplified score that was actually written | both |
| Final output | `<stem>_simplification_report.json` | How much the LH actually changed (issue #47) | both |
| Run-level | `run_summary.json` | One-glance index of the whole run (see below) | both |
| Run-level | `piano_learning.log` | Full run log, including which backend ran | both |

\* `<stem>_analysis.json` is written by the `generate_analysis_of_musicxml`
sub-command / end-to-end flow, not by the simplifier backends themselves.

The model output and reasoning are written **before** the plan is validated, so a
run that fails extraction or validation still leaves the raw response and a
`validation_report.json` explaining why it failed.

Load-bearing names -- `<stem>_analysis.json`, `<stem>_simplified.musicxml`, and
`<stem>_simplification_report.json` -- are consumed by `run_e2e.sh` and the
`compare_runs` sub-command. They are pinned in `run_artifacts.ARTIFACT_SPECS` and
guarded by `tests/test_run_artifacts.py`; renaming them breaks those consumers.

## Answering common questions

* **What was sent to the model?** `_prompt_system.txt`, `_prompt_user.txt`,
  `_prompt_compact_analysis.json`, `_prompt_plan_schema.json`.
* **What did the model return?** `_model_output_raw.txt` (and
  `_model_reasoning.txt`).
* **What failed validation?** `_validation_report.json` (`status: failed` with the
  error), alongside the raw output that produced it.
* **What was finally written?** `_simplified.musicxml`, summarized by
  `_simplification_report.json`.
* **What did this run do overall?** `run_summary.json`.

## `run_summary.json`

A single per-run index. Fields that only apply to the OpenAI path (`request`,
`validation`) are omitted for the music21 backend.

```json
{
  "schemaVersion": 1,
  "input": {"source": "musicxml", "path": "user/input/Song.musicxml", "stem": "Song"},
  "simplifier": "openai",
  "mode": "responses_background",
  "model": "gpt-5.5",
  "request": {"timeoutSeconds": 900, "maxOutputTokens": 24000, "reasoningEffort": "medium", "reasoningSummary": "detailed"},
  "outcome": "success",
  "error": null,
  "reportHighlights": {"measuresTotal": 20, "measuresChanged": 12, "pctChanged": 60.0, "lhNoteDelta": -40, "unmodifiedFlag": false},
  "validation": {"status": "passed", "error": null},
  "artifacts": [
    {"role": "prompt_system", "file": "Song_prompt_system.txt", "exists": true}
  ]
}
```

* `mode` is `responses_background` or `agent` (OpenAI), `manual` (prompt rendering
  only), or `local` (music21).
* `outcome` is `success` or `failed`. On failure, `error` carries the message and
  the `artifacts` list shows which files were reached (`exists: false` for the
  ones a failed run never produced).
* `artifacts` lists every artifact the backend can produce and whether it made it
  to disk -- the honest record of how far the run got.

## Reserved: targeted repair (#70)

The targeted-repair flow is not implemented yet. When it lands, per-attempt plans
use the reserved name `<stem>_repair_attempt_NN.json` (see
`run_artifacts.repair_attempt_filename`) so they slot into this same flat layout
without another rename.
