# Copilot Instructions for Piano-Learning

## Project Overview
- **Purpose:** Tools and scripts for learning, processing, and converting piano music, including MusicXML, PDF, and MIDI workflows.
- **Key Directories:**
  - `user/input/`: Source music files (MusicXML, PDF, etc.)
  - `user/output-*`: Output directories for processed results
  - `main.py`: Main entry point for running music processing tasks via sub-commands.

## Environment Setup
- Use Python 3.10+ and Ubuntu (see `README.md` for full setup commands)
- Always use a virtual environment (`python -m venv .venv && source .venv/bin/activate`)
- Install dependencies with `pip install -r requirements.txt`
- Java and tools like Audiveris, LilyPond, and MuseScore are required for some workflows (see `README.md` for install commands)
- Pre-commit is used for linting: `pre-commit install` and `pre-commit run --all-files`

## Quickstart
- Create and activate a venv, then install deps:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
- Put inputs in `user/input/`
- Discover available sub-commands and options:
  - `python main.py -h`
  - `python main.py <sub-command> -h`

## Developer Workflows
- **Typical run:**
  - Place input files in `user/input/`
  - Run `main.py` with a sub-command (e.g., `convert_pdf_to_musicxml`) to process files.
  - Outputs are written to `user/output-YYYY-MM-DD/` directories.
- **Adding new processing logic:**
  - Add new scripts or modules in the root or under `user/`
  - Add a new sub-command to `main.py` to expose the functionality.
  - Keep CLI help up to date (arguments, descriptions, examples).
- **Discovering commands:**
  - `python main.py -h` lists all sub-commands
  - `python main.py <sub-command> -h` shows options for a specific command

- **Testing:**
  - No formal test suite; validate by running scripts on sample files

## Project Conventions
- Output directories are date-stamped (e.g., `output-2025-09-16/`)
- Input files are not modified; outputs are always written to new folders
- Use clear, descriptive names for new scripts and modules
- Keep dependencies minimal and document any new requirements in `requirements.txt` and `README.md`
- Output layout:
  - `user/output-YYYY-MM-DD/<task-or-module>/<basename>/...` (use a sensible subfolder structure per task)

## Integration Points
- External tools (Audiveris, LilyPond, MuseScore) are invoked via shell commands; ensure they are installed and on PATH
- MusicXML, PDF, and MIDI files are the primary data formats
- Verify tools are accessible:
  - `audiveris -version`, `lilypond --version`, `mscore --version` or `musescore4 --version`

## Examples
- To convert a PDF to MusicXML:
  - `python main.py convert_pdf_to_musicxml user/input/your_file.pdf`
- To analyze a MusicXML file:
  - `python main.py analyze_musicxml user/input/your_file.musicxml`
- To convert a MusicXML file to PDF:
  - `python main.py convert_musicxml_to_pdf user/input/your_file.musicxml`
- List commands and help:
  - `python main.py -h`
  - `python main.py <sub-command> -h`

## References
- See `README.md` for full setup and tool installation
- Example input files: `user/input/`
- Example outputs: `user/output-*/`

## Maintaining this file
- Update “Examples” and “Developer Workflows” when adding/removing sub-commands in `main.py`.
- Reflect any new external tool requirements in “Environment Setup” and “Integration Points”.
- Keep output layout notes aligned with actual directory structure produced by commands.
