# Documentation & commenting standards

How we comment and document Python in this repo. The goal is not maximum
coverage; it is a high signal-to-noise ratio for the next developer (or LLM)
reading the code. Follow PEP 257 and the style already in the tree.

## The core rule

**Document what requires understanding; do not narrate what the code already
says.** A comment or docstring earns its place when it explains at least one of:

- why the code exists;
- its behavioral contract (what a caller can rely on);
- an important invariant;
- a non-obvious domain assumption (music theory, MusicXML/music21 quirks);
- a surprising edge case or fallback strategy;
- a side effect;
- a library/interoperability constraint;
- why an apparently simpler implementation would be wrong.

Before keeping any comment, ask: *if this line disappeared, would a competent
Python developer lose information they could not quickly infer from the code?*
If no, delete it.

Do **not** add comments that merely translate Python into English:

```python
# Bad -- restates the code
# Iterate over the measures.
for measure in measures:
    ...

# Bad -- restates the return
# Return the last part.
return parts[-1]
```

## Public functions

Give every non-trivial public function a concise docstring covering its contract,
non-obvious behavior, important side effects, and error conditions that are part
of the API. Do **not** repeat types already stated in the signature.

```python
def needs_build(src: Path, dst: Path, *, overwrite: bool) -> bool:
    """Return whether `dst` should be rebuilt from `src`.

    Rebuild when explicitly requested, when the destination is missing, or when
    the source is newer than the destination.
    """
```

## Private functions

No docstring is required on every helper. Leave tiny, obvious helpers bare.
Add a short docstring when a private function embodies real domain knowledge,
validation rules, a fallback convention, or a non-obvious algorithm -- for
example, the helper that picks the left-hand part by clef and falls back to
staff order, or the plan timing validator that enforces gap/overlap/coverage.

## Inline comments

Explain **why**, not **what**. Preserve comments that record a real domain or
compatibility decision; rewrite ones that have gone stale, misleading, or
conversational.

```python
# Good
# No unambiguous clef signal: fall back to the RH-then-LH ordering convention.
return parts[-1]
```

## Module docstrings

Use one when it explains the module's responsibility or architectural role
(e.g. "this owns artifact naming so names can't drift"). Skip boilerplate like
`"""Utility functions."""`. Never open a module with a stale filename banner or
usage line that no longer matches how the code is invoked.

## Dataclasses and models

Document a dataclass when its role or fields carry domain meaning; skip it when
field names and context already make the container obvious.

## Style

- Prefer one-line docstrings when one line is enough; go multi-line only for
  genuinely additional context.
- Do not add `Args:` / `Returns:` / `Raises:` sections purely for completeness --
  only when they say something the signature does not.
- Avoid decorative headings and comments that will rot (line-by-line narration,
  "FIX for X", debugging diaries). Convert any historical wording into a timeless
  statement of the underlying behavior.

## Repo-specific hot spots

These areas reward careful documentation because the behavior is not obvious from
the code alone:

- MusicXML rewriting and part/measure parity checks;
- left-hand vs. right-hand identification (clef detection + fallback);
- measure numbering and pickup/anacrusis handling; measure-duration math;
- simplification-plan validation and the plan contract (the AI never emits
  MusicXML -- see `docs/ARCHITECTURE.md`);
- timing coverage/gap/overlap validation and truncation detection;
- OpenAI/model response handling;
- score-analysis heuristics (texture classification, prescriptive layer);
- artifact/report semantics (`run_artifacts.py`, `simplification_report.py`).
