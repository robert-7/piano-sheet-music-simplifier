---
name: changing-the-plan-schema
description: Use when modifying the shape of the left-hand simplification-plan JSON -- adding/removing/renaming fields, changing textures, or altering validation rules. Ensures every coupled touchpoint (schema, validator, rewriter, prompts, tests) stays in sync.
---

# Changing the simplification-plan schema

The plan JSON is the contract between the AI backend and the deterministic MusicXML rewriter. The
model emits a compact plan; **local code owns all MusicXML generation** (the AI must never emit
MusicXML). Because the plan shape is referenced in five places, changing it in one place and not the
others silently breaks the pipeline -- validation passes but the rewrite is wrong, or the model is
prompted for a field the validator rejects.

## The rule

If you change the plan JSON shape, you MUST update **all** of the touchpoints below, then verify.
Do not stop after the schema -- treat the checklist as atomic.

## Touchpoints (update every one)

1. **Schema** -- `src/piano_learning/utils/simplification_plan.py`, `get_plan_schema()`.
   The JSON Schema the model is constrained to. Add/rename/remove the field here first.
2. **Validator** -- same file, `validate_plan()` and its helpers `_validate_measure()`,
   `_validate_event()`, `_validate_measure_timing()`. Enforce any new invariants; relax any rule the
   change makes obsolete. Existing rejects include: unsupported schema/scope, missing/extra
   measures, bad textures, events shorter than an eighth note, >3 simultaneous LH notes, and -- for
   non-`preserve` measures -- timing gaps/overlaps or failure to cover the full source measure
   duration. A `preserve` measure must carry no events.
3. **Rewriter** -- `src/piano_learning/utils/musicxml_rewriter.py`,
   `write_simplified_musicxml_from_plan()` / `apply_plan_to_score()`. This consumes the validated
   plan and writes the LH part. If the field affects the rendered notes, wire it in here.
4. **Prompts** -- the `.j2` templates in `src/piano_learning/resources/`
   (`system_instructions_for_chatgpt.j2`, `user_prompt_for_chatgpt.j2`). Teach the model the new
   shape and any new constraints. Keep the "never emit MusicXML" and prescriptive-field guidance
   intact.
5. **Tests** -- `tests/test_simplification_plan.py`. Add cases for the new field: a valid plan that
   uses it, and invalid plans that exercise each new reject path. Follow the existing test style.

## Verify

Run the suite and pre-commit through the venv (never system Python):

```bash
.venv/bin/python -m unittest tests.test_simplification_plan -v
.venv/bin/pre-commit run --all-files
```

If the AI backend is reachable, do an end-to-end `--simplifier openai` run and check the
`<stem>_simplification_report.json` -- `pctChanged` and the texture histogram should reflect the new
behavior, and `unmodifiedFlag` should not be set for a score that ought to change.

## Musical sanity check

Beyond passing tests, confirm the change produces *playable* LH output for an intermediate pianist --
that is the whole point. A schema that validates but yields awkward stretches, muddy low-register
clusters, or textures that fight the RH is a regression even if green.
