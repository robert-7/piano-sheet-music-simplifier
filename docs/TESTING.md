# Testing

The suite is `unittest`, not `pytest` (see [`CLAUDE.md`](../CLAUDE.md) for the run commands). This
page covers what's in [`tests/`](../tests/) and why, so regressions in LH simplification stay
caught instead of relying on manual inspection.

## Running the tests

```bash
# Full suite
.venv/bin/python -m unittest discover -s tests -v

# One module / class / method
.venv/bin/python -m unittest tests.test_simplification_plan.SimplificationPlanTests.test_validate_plan_rejects_missing_measure

# Everything pre-commit enforces (lint + pyright + tests)
.venv/bin/pre-commit run --all-files
```

A failure means one of: the plan validator rejected (or wrongly accepted) something, the rewriter
changed RH content or measure structure it shouldn't have, or a report/artifact calculation drifted.
Read the assertion message first -- most tests assert on the specific invariant they exist to guard,
named in the test itself.

## Shared fixtures ([`tests/fixtures.py`](../tests/fixtures.py))

Score builders used across multiple test modules, so a new regression test doesn't need to hand-roll
a `music21.stream.Score`:

| Builder | Shape | Exercises |
| --- | --- | --- |
| `two_measure_broken_arpeggio_score` | 2 measures, busy 16th-note LH arpeggio | Beat-window reduction collapsing a dense texture |
| `alberti_bass_score` | 2 measures, classic low-high-mid-high LH | Reduction leaving an already-beat-aligned texture intact |
| `walking_bass_score` | 2 measures, single-note-per-beat LH line | Reduction being a no-op on an already-simple texture |
| `pickup_measure_score` | 1-beat pickup (measure 0) + one full 4/4 measure | Anacrusis measure-duration and plan handling |
| `score_with_repeat_barlines` | 2 measures, repeat-start on m1 / repeat-end on m2 | Repeat barlines surviving an LH-only rewrite |

Add a new builder here (not inline in a test) when a fixture is likely to be reused, per the
project's [reusable-fixtures convention](https://github.com/robert-7/piano-sheet-music-simplifier/issues/71).

## What's covered, and why

- **Truncated / partial model output** (`test_simplification_plan.py`) -- a model response containing
  a truncation marker (`TRUNCATED`, `[...continued`, a trailing ellipsis) is rejected before it ever
  reaches the rewriter. Regression for issue #81, where a legitimate ellipsis *inside* a JSON string
  value was misread as truncation.
- **Measure parity** (`test_simplification_plan.py`, `test_musicxml_rewriter.py`) -- a plan missing a
  source measure, or referencing one that doesn't exist, is rejected; `validate_musicxml_against_source`
  checks the written output's measure numbering matches the source per part.
- **Pickup / anacrusis measures** (`test_pickup_handling.py`) -- a pickup measure is conventionally
  numbered 0 with a notated duration shorter than its time signature's bar length. Two related bugs
  are guarded here: `_measure_duration_ql` previously reported the full bar duration for a pickup
  (ignoring `paddingLeft`), and the plan validator previously rejected measure number 0 outright,
  making it impossible to ever simplify a pickup's LH.
- **Repeat preservation** (`test_repeat_preservation.py`) -- start/end repeat barlines on both hands
  must survive an LH-only rewrite. The rewriter only ever clears `Voice`/`GeneralNote`/`Chord`
  elements from a measure, so barlines are untouched by construction; this test guards that invariant
  explicitly rather than relying on that implementation detail staying true.
- **Round-trip parseability** (`test_musicxml_roundtrip.py`) -- output written by
  `write_simplified_musicxml_from_plan` must re-parse as a `music21.stream.Score` with the same part
  count and measure numbering as the source. Complements the hard MusicXML validation added for
  issue #66, which runs during the write itself.
- **Common LH textures** (`test_generate_simplified_musicxml_using_music21.py`) -- broken-arpeggio,
  Alberti bass, and walking-bass patterns fed through the local `music21` backend's beat-window
  reduction, checking it collapses busy textures without disturbing textures that are already
  beginner-appropriate.

## Style

Follow `test_simplification_plan.py`: plain `unittest.TestCase`, one behavior per test, real
`music21` objects rather than mocks except at the OpenAI API boundary (see
`test_generate_simplified_ai.py` for that pattern). See the [Test coverage](../CLAUDE.md) note in
`CLAUDE.md` for when a change needs a new test.
