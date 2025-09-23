# Piano Learning

## Getting Set Up

Please reference [SETUP.md](SETUP.md) for setup steps.

## How to Generate a Simplified Sheet

Given a sheet located at `user/input/Difficult_Sheet_Music.pdf`.

1. To convert a PDF to MusicXML:
  * Run `python main.py convert_pdf_to_musicxml --out-dir user/output/TIMESTAMP user/input/Difficult_Sheet_Music.pdf`
2. To analyze a MusicXML file:
  * Run `python main.py generate_analysis_of_musicxml --out-dir user/output/TIMESTAMP user/input/Difficult_Sheet_Music.xml`
3. To generate the simplified MusicXML file, we use one of two methods: the programmatic way (recommended) or manual way (legacy, for validation):
  1. (Automatic, recommended) Run `python main.py generate_analysis_of_musicxml user/input/Difficult_Sheet_Music.xml`
  2. (Manual, for validation) We use the ChatGPT UI ("ChatGPT 5 Thinking" model) to generate the simplified MusicXML file.
    1. Run `python main.py generate_simplified_musicxml --manual user/input/Difficult_Sheet_Music.xml` to generate the prompt.
    2. Note: This templates the files below to generate the total prompt:
      1. System prompt: `src/piano_learning/resources/system_instructions_for_chatgpt.j2`
      2. User prompt: `src/piano_learning/resources/user_prompt_for_chatgpt.j2`
    3. Attach the `user/input/Difficult_Sheet_Music.xml` and `user/input/Difficult_Sheet_Music_analysis.json` files.
    4. Run the prompt and download the generated simplified file. Save it as `user/input/Difficult_Sheet_Music_simplified.xml`.
      * Note: Re-run the prompt if something goes wrong (TODO: Install output guardrails)

    Option: print the prompts via CLI with variables filled automatically, then copy/paste into ChatGPT:

    ```bash
    ./main.py generate_simplified_musicxml --manual "user/input/Kakariko_Village.xml"
    ```
4. To convert the simplified MusicXML file to PDF:
  * Run `python main.py convert_musicxml_to_pdf --out-dir user/output/TIMESTAMP user/input/Difficult_Sheet_Music_simplified.xml`

If you require List commands and help:
  * `python main.py -h`
  * `python main.py <sub-command> -h`

## Validating the External Dependencies

This repo makes use of various external tools.

### Debugging Issues with OpenAI

For additional details for validating issues:

* [OpenAI's Observability](https://platform.openai.com/logs)

Moreover, for validating the agent, use the `--manual` argument to output the prompts to paste into ChatGPT.
Run `python main.py generate_simplified_musicxml --manual user/input/Difficult_Sheet_Music.xml` to generate the prompt.
