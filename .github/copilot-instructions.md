# Copilot Instructions for Piano-Learning

## Project Overview

* Purpose: Tools and scripts for converting, analyzing, and simplifying piano sheet music. Primary formats are PDF and MusicXML; outputs include MusicXML and PDF.
* Key directories:
    * `user/input/`: Source music files (PDF, MusicXML)
    * `user/output/TIMESTAMP/`: Destination for generated outputs (pass with global `--out-dir`)
    * `src/piano_learning/resources/`: Prompts and resources (e.g., `system_instructions_for_chatgpt.j2`, `user_prompt_for_chatgpt.j2`)
    * `main.py`: CLI entry point exposing sub-commands

## Environment Setup

* OS: Ubuntu recommended. Python: 3.10-3.13 supported.
* Use a virtual environment:
    * `python -m venv .venv && source .venv/bin/activate`
    * `pip install -r requirements.txt`
* Pre-commit for linting:
    * `pre-commit install`
    * `pre-commit run --all-files`
* External tools required for end-to-end workflows (see `SETUP.md` for commands):
    * OpenJDK 17
    * Audiveris 5.7.1 (PDF → MusicXML)
    * LilyPond (Music engraving)
    * MuseScore (optional rendering/conversion)
* Environment variables:
    * Copy `.env.template` to `.env` and set `OPENAI_API_KEY`

See `SETUP.md` for step-by-step install commands (apt, snap, Audiveris .deb, and verification).

## Quickstart

* Prepare environment (venv + dependencies) and install external tools per `SETUP.md`.
* Place inputs in `user/input/`.
* Discover available sub-commands and options:
    * `python main.py -h`
    * `python main.py <sub-command> -h`
* End-to-end in one command (generate final simplified PDF):
    * From PDF: `./main.py generate_simplified_pdf --pdf_path user/input/Your_Score.pdf`
    * From MusicXML: `./main.py generate_simplified_pdf --musicxml_path user/input/Your_Score.musicxml`
* Create a simplified MusicXML (automatic, recommended):
    * `python main.py generate_simplified_musicxml user/input/Your_Score.musicxml`
* Create manual prompts (alternative):
    * `python main.py generate_simplified_musicxml --manual user/input/Your_Score.musicxml`

## Developer Workflows

### End-to-End run

1. End-to-end in one command (generate final simplified PDF):
    * From PDF: `./main.py generate_simplified_pdf --pdf_path user/input/Your_Score.pdf`
    * From MusicXML: `./main.py generate_simplified_pdf --musicxml_path user/input/Your_Score.musicxml`

### Run one command at a time

1. Convert a PDF to MusicXML:
    * `python main.py convert_pdf_to_musicxml user/input/Your_Score.pdf`
1. Generate an analysis for a MusicXML file:
    * `python main.py generate_analysis_of_musicxml user/input/Your_Score.musicxml`
1. Create a simplified MusicXML:
    * Automatic (recommended):
        * `python main.py generate_simplified_musicxml user/input/Your_Score.musicxml`
    * Manual (alternative, copy/paste prompts into ChatGPT):
        1. `python main.py generate_simplified_musicxml --manual user/input/Your_Score.musicxml`
        1. Note: This renders `src/piano_learning/resources/system_instructions_for_chatgpt.j2` and `src/piano_learning/resources/user_prompt_for_chatgpt.j2` with BASENAME and TIMESTAMP.
        1. Attach `user/input/Your_Score.musicxml` and `user/input/Your_Score_analysis.json`
        1. Save the result as `user/input/Your_Score_simplified.musicxml`
1. Render the simplified MusicXML to PDF:
    * `python main.py convert_musicxml_to_pdf user/input/Your_Score_simplified.musicxml`

## Project Conventions

Inputs are never modified; outputs go to the directory specified by the global `--out-dir`. Use timestamped subdirectories under `user/output/` (i.e., `user/output/TIMESTAMP/`).

## Integration Points

* External tools invoked via shell commands; ensure they are on PATH.
* Quick checks (see `SETUP.md` for full details):
    * `audiveris -version`
    * `lilypond --version`
    * `snap list musescore` (if installed via snap)

## Examples

* End-to-end (generate final simplified PDF):
    * From PDF: `./main.py generate_simplified_pdf --pdf_path user/input/your_file.pdf`
    * From MusicXML: `./main.py generate_simplified_pdf --musicxml_path user/input/your_file.musicxml`
* Convert PDF → MusicXML:
    * `python main.py convert_pdf_to_musicxml user/input/your_file.pdf`
* Analyze MusicXML:
    * `python main.py generate_analysis_of_musicxml user/input/your_file.musicxml`
* Create simplified MusicXML (automatic):
    * `python main.py generate_simplified_musicxml user/input/your_file.musicxml`
* Create simplified MusicXML (manual prompts):
    * `python main.py generate_simplified_musicxml --manual user/input/your_file.musicxml`
* Convert MusicXML → PDF:
    * `python main.py convert_musicxml_to_pdf user/input/your_file.musicxml`
* List commands and help:
    * `python main.py -h`
    * `python main.py <sub-command> -h`

## Troubleshooting & References

* See `README.md` for the end-to-end workflow, and `SETUP.md` for installation commands.
* OpenAI debugging: [OpenAI's Observability](https://platform.openai.com/logs)
* Prompt references:
    * System: `src/piano_learning/resources/system_instructions_for_chatgpt.j2`
    * User: `src/piano_learning/resources/user_prompt_for_chatgpt.j2`

## Maintaining this file

* Update "Examples" and "Developer Workflows" when adding/removing sub-commands in `main.py`.
* Reflect any new external tool requirements (versions, install steps) in "Environment Setup" and "Integration Points".
* Keep output directory guidance aligned with the actual structure produced by commands (timestamped `user/output/TIMESTAMP/`).
* Reflect any new external tool requirements (versions, install steps) in "Environment Setup" and "Integration Points".
* Keep output directory guidance aligned with the actual structure produced by commands.
