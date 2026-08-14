# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Contributor mindset

When contributing to this codebase, act as both an **expert piano arranger and copyist** and a
software engineer. Every decision -- texture choices, simplification heuristics, plan schema, prompt
wording -- should be evaluated from the perspective of the end user: an intermediate pianist trying
to play a piece that was previously beyond their reach. Prefer musical correctness and playability
over technical elegance when the two conflict.

## What this is

A CLI that takes difficult piano sheet music (PDF or MusicXML) and produces an easier-to-play
version. The core idea is **left-hand simplification**: the right hand and overall structure are
preserved, only the LH part is rewritten to a simpler texture.

## Commands

Always run Python commands inside the project virtualenv (activate with `source .venv/bin/activate`
or prefix commands with `.venv/bin/python` / `.venv/bin/pre-commit`). Never rely on the system
Python.

```bash
# Run the full test suite (unittest, no pytest)
.venv/bin/python -m unittest discover -s tests -v

# Run a single test module / class / method
.venv/bin/python -m unittest tests.test_simplification_plan
.venv/bin/python -m unittest tests.test_simplification_plan.SomeTestCase.test_something

# Lint + type-check + tests all run through pre-commit
.venv/bin/pre-commit run --all-files

# Type-check just src/ (pyright, standard mode; config in pyrightconfig.json)
.venv/bin/pyright
```

**Before marking any task complete**, run `pre-commit run --all-files` (via the venv) and fix any
failures. This is the single gate that enforces formatting, type safety, and test correctness.

Note: `pre-commit` runs both `pyright` and the unittest suite as hooks (see
`.pre-commit-config.yaml`). The `pyright` hook is a ratchet -- it only checks files touched in the
commit, so pre-existing type debt does not block you but new debt in touched files does. Both hooks
run in isolated pre-commit envs, so their pinned deps must be kept in sync with `requirements.txt`.

CI (`.github/workflows/pre-commit.yml`) runs pre-commit across Python 3.11-3.14.

## Running the pipeline

Inputs live in `user/input/`; outputs go to a timestamped `user/output/TIMESTAMP/` (override with
the global `--out-dir`). **Inputs are never modified.** Every run also writes `piano_learning.log`
to the output dir -- the fastest way to confirm which backend ran.

```bash
# End-to-end (PDF or MusicXML in, simplified PDF out)
./main.py generate_simplified_pdf --pdf_path user/input/Your_Score.pdf
./main.py generate_simplified_pdf --musicxml_path user/input/Your_Score.musicxml

# Individual steps
python main.py convert_pdf_to_musicxml user/input/Your_Score.pdf      # Audiveris
python main.py generate_analysis_of_musicxml user/input/Your_Score.musicxml
python main.py generate_simplified_musicxml user/input/Your_Score.musicxml
python main.py convert_musicxml_to_pdf user/input/Your_Score.musicxml # MuseScore by default
python main.py compare_runs <runA> <runB>                            # diff two runs' reports

python main.py -h            # list sub-commands
python main.py <cmd> -h      # per-command help
```

## Architecture

Before making structural changes -- adding sub-commands, touching the pipeline stages, changing how
backends are selected, or modifying external-tool invocations -- read `ARCHITECTURE.md` first. It is
the authoritative source for how the pieces fit together. Keep the Mermaid diagram in sync; the
pre-commit hook (`scripts/diagram.sh`) will catch drift.

`main.py` is a thin argparse dispatcher; each sub-command lives in
`src/piano_learning/commands/` and shared logic in `src/piano_learning/utils/`. The pipeline (see
`ARCHITECTURE.md` for the diagram) is:

```plaintext
PDF --(Audiveris)--> MusicXML --> analysis JSON --> LH simplification-plan JSON
    --(deterministic rewrite)--> simplified MusicXML --(MuseScore/LilyPond)--> PDF
```

### Two simplifier backends (`--simplifier`, default `music21`)

- **`music21`**: fully local/deterministic LH reduction. No API key needed.
  (`generate_simplified_musicxml_using_music21.py`)
- **`openai`**: requires `OPENAI_API_KEY`. Runs harmony analysis, sends a *compact* analysis to the
  model, and gets back a **left-hand simplification-plan JSON** -- never MusicXML.
  (`generate_simplified_musicxml_using_ai.py`)

Backend selection is resolved in `main.py` (`resolve_simplifier` / `validate_simplifier_args`).
`--use-agent` (experimental Agents SDK) and `--manual` (render prompts only, no API call) apply
**only** with `--simplifier openai`. The default OpenAI path is the Responses API in background
mode. `--music21` is a deprecated alias.

### The plan contract (the crux of the design)

The AI **must not emit MusicXML**. It returns a compact JSON plan; local code owns all MusicXML
generation. This split is enforced hard:

- `simplification_plan.py` -- defines the schema (`get_plan_schema`), builds the compact analysis
  (`compact_analysis_for_plan`), extracts JSON from model output, and **validates** the plan
  (`validate_plan`). Validation rejects: unsupported schema/scope, missing/extra measures, bad
  textures, events shorter than an eighth note, >3 simultaneous LH notes, and -- for non-`preserve`
  measures -- timing gaps/overlaps or failure to cover the full source measure duration. A measure
  marked `preserve` keeps the original LH untouched and must carry no events.
- `musicxml_rewriter.py` -- copies the source score, preserves RH + structure, and rewrites only the
  LH part from the validated plan (`write_simplified_musicxml_from_plan`, `apply_plan_to_score`),
  then checks measure parity against the source.

If you change the plan JSON shape, you must update **all** of: the schema in
`simplification_plan.py`, `validate_plan`, the rewriter, the `.j2` prompts in
`src/piano_learning/resources/`, and `tests/test_simplification_plan.py`.

## Test coverage

Write tests for any non-trivial logic you add or change. Coverage is not measured by a hard
threshold, but the principle is: if it can break silently, it should have a test. Good targets are
validation logic, rewriter edge cases, report calculations, and any new plan-schema rules. Keep
tests in the existing `tests/` directory using `unittest`; use the patterns already established in
`test_simplification_plan.py` as the style reference.

### Instrumentation (issue #47)

Every run (both backends) emits `<stem>_simplification_report.json` quantifying how much the LH
actually changed -- measures preserved vs. changed, `pctChanged`, texture histogram, LH note-count
delta, and (AI path) how many `prescriptiveLH` recommendations were followed vs. overridden. An
`unmodifiedFlag` warns loudly when a run barely touched the source. `compare_runs` diffs two
reports so simplification regressions are visible run over run. See `simplification_report.py`.

Note `prescriptiveLH` is the one analysis field the model is told to **follow by default**; the
system prompt otherwise tells it to ignore prescriptive fields.

## External tools

Invoked via shell; must be on `PATH` (resolved with `shutil.which`):

- **Audiveris** (5.7.x, needs Java/OpenJDK 17) -- PDF → MusicXML
- **MuseScore** -- preferred PDF renderer (`--convert-with-musescore`, default)
- **LilyPond** -- optional alternative renderer (`--convert-with-lilypond`)

The Docker image (`Dockerfile` / `docker-compose.yml`) bundles MuseScore + LilyPond with a headless
Qt env, so rendering works out of the box:

```bash
docker compose run --rm piano-learning python3 main.py generate_simplified_pdf --musicxml_path user/input/Your_Score.musicxml
```

See `SETUP.md` for local install steps.

## Config

- `.env` (copy from `.env.template`): `OPENAI_API_KEY` (only for `--simplifier openai`), optional
  `OPENAI_MODEL` / `OPENAI_AGENT_MODEL`, and `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR/CRITICAL).
- `ARCHITECTURE.md` contains a Mermaid diagram validated by a pre-commit hook (`scripts/diagram.sh`)
  -- keep it in sync when sub-commands change.
