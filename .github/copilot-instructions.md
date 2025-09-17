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

## Developer Workflows
- **Typical run:**
  - Place input files in `user/input/`
  - Run `main.py` with a sub-command (e.g., `convert_pdf_to_musicxml`) to process files.
  - Outputs are written to `user/output-YYYY-MM-DD/` directories.
- **Adding new processing logic:**
  - Add new scripts or modules in the root or under `user/`
  - Add a new sub-command to `main.py` to expose the functionality.
- **Testing:**
  - No formal test suite; validate by running scripts on sample files

## Project Conventions
- Output directories are date-stamped (e.g., `output-2025-09-16/`)
- Input files are not modified; outputs are always written to new folders
- Use clear, descriptive names for new scripts and modules
- Keep dependencies minimal and document any new requirements in `requirements.txt` and `README.md`

## Integration Points
- External tools (Audiveris, LilyPond, MuseScore) are invoked via shell commands; ensure they are installed and on PATH
- MusicXML, PDF, and MIDI files are the primary data formats

## Examples
- To convert a PDF to MusicXML:
  - `python main.py convert_pdf_to_musicxml user/input/your_file.pdf`
- To analyze a MusicXML file:
  - `python main.py analyze_musicxml user/input/your_file.musicxml`
- To convert a MusicXML file to PDF:
  - `python main.py convert_musicxml_to_pdf user/input/your_file.musicxml`

## References
- See `README.md` for full setup and tool installation
- Example input files: `user/input/`
- Example outputs: `user/output-*/`

---
For questions or improvements, update this file to help future AI agents and developers.
