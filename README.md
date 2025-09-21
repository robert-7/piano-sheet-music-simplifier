# Piano Learning

## Getting Set Up

Please reference [SETUP.md](SETUP.md) for setup steps.

## How to Generate a Simplified Sheet

Given a sheet located at `user/input/Difficult_Sheet_Music.pdf`.

1. To convert a PDF to MusicXML:
  * Run `python main.py convert_pdf_to_musicxml --out-dir user/output user/input/Difficult_Sheet_Music.pdf`
2. To analyze a MusicXML file:
  * Run `python main.py generate_analysis_of_musicxml --out-dir user/output user/input/Difficult_Sheet_Music.xml`
3. We use the ChatGPT UI to generate the simplified MusicXML file.
  1. In ChatGPT ("ChatGPT 5 Thinking" model), use the two-part prompt (templated with Jinja2):
    - System prompt: `src/piano_learning/resources/system_instructions_for_chatgpt.j2`
    - User prompt: `src/piano_learning/resources/user_prompt_for_chatgpt.j2`
  2. Replace variables when pasting (or render them locally). Variables:
    - `{{ BASENAME }}`: e.g., `Difficult_Sheet_Music`
    - `{{ TIMESTAMP }}`: e.g., `20250101-120000`
  3. Attach the `user/input/Difficult_Sheet_Music.xml` and `user/input/Difficult_Sheet_Music_analysis.json` files.
  4. Run the prompt and download the generated simplified file. Save it as `user/input/Difficult_Sheet_Music_simplified.xml`. Re-run the prompt if something goes wrong (TODO: Install output guardrails)
4. To convert the simplfied MusicXML file to PDF:
  * Run `python main.py convert_musicxml_to_pdf --out-dir user/output user/input/Difficult_Sheet_Music_simplified.xml`

If you require List commands and help:
  * `python main.py -h`
  * `python main.py <sub-command> -h`

## Validating the External Dependencies

This repo makes use of various external tools.

### Debugging Issues with OpenAI

For additional details for validating issues:

* [OpenAI's Observability](https://platform.openai.com/logs)

Moreover, for validating the agent, use the split prompts with an example user-provided MusicXML file:

- System prompt: [`system_instructions_for_chatgpt.j2`](src/piano_learning/resources/system_instructions_for_chatgpt.j2)
- User prompt: [`user_prompt_for_chatgpt.j2`](src/piano_learning/resources/user_prompt_for_chatgpt.j2)

### Optional: render templates from the command line

If you want to render the `.j2` files without running the Python command, you can do it with a small Python one-liner:

```
python - <<'PY'
from pathlib import Path
from src.utils.template_utils import render_template_file
ctx = {"BASENAME": "Difficult_Sheet_Music", "TIMESTAMP": "20250101-120000"}
base = Path('src/piano_learning/resources')
print(render_template_file(base / 'system_instructions_for_chatgpt.j2', ctx))
print('\n' + '='*80 + '\n')
print(render_template_file(base / 'user_prompt_for_chatgpt.j2', ctx))
PY
```

Or install `jinja2-cli` if you prefer a pure CLI tool:

```
pip install jinja2-cli
jinja2 src/piano_learning/resources/system_instructions_for_chatgpt.j2 -D BASENAME=Difficult_Sheet_Music -D TIMESTAMP=20250101-120000
jinja2 src/piano_learning/resources/user_prompt_for_chatgpt.j2 -D BASENAME=Difficult_Sheet_Music -D TIMESTAMP=20250101-120000
```
