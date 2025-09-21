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
  1. In ChatGPT ("ChatGPT 5 Thinking" model), use the two-part prompt:
     - System prompt: `src/piano_learning/resources/system_instructions_for_chatgpt.txt`
     - User prompt: `src/piano_learning/resources/user_prompt_for_chatgpt.txt`
  2. Update the `${BASENAME}` variable with `Difficult_Sheet_Music` and the timestamp with the timestamp of your choice.
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

- System prompt: [`system_instructions_for_chatgpt.txt`](src/piano_learning/resources/system_instructions_for_chatgpt.txt)
- User prompt: [`user_prompt_for_chatgpt.txt`](src/piano_learning/resources/user_prompt_for_chatgpt.txt)
