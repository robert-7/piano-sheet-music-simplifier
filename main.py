#!/usr/bin/env python3
import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.commands import convert_musicxml_to_pdf
from src.commands import convert_pdf_to_musicxml
from src.commands import generate_analysis_of_musicxml
from src.commands import generate_legacy_analysis_of_musicxml
from src.commands import generate_simplified_musicxml
from src.utils import fs_utils

logger = logging.getLogger(__name__)



def build_parser() -> argparse.ArgumentParser:
    """
    Builds the command-line argument parser.

    This parser provides sub-commands for processing piano music files, including:
    - Converting PDFs to MusicXML
    - Analyzing MusicXML files
    - Generating simplified MusicXML files
    - Converting MusicXML to PDF

    Each sub-command expects input files from 'user/input/' and writes outputs to a date-stamped directory under 'user/output-*/'.
    External tools (e.g., Audiveris, LilyPond, MuseScore) are invoked as needed.

    See README.md for usage examples and setup instructions.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    default_out_dir = Path(f"./user/output-{timestamp}")
    fs_utils.ensure_dir(default_out_dir)

    # Create the top-level parser with sub-commands
    parser = argparse.ArgumentParser(description="Process sheet music files: analyze harmony, convert to PDF, or process PDFs.")
    # NEW: global log file option (logs to console and this file)
    parser.add_argument(
        "--log-file",
        type=Path,
        default=default_out_dir / "piano_learning.log",
        help="Path to a log file (console logs are also emitted).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Sub-parser for convert_pdf_to_musicxml ---
    pdf_parser = subparsers.add_parser("convert_pdf_to_musicxml", help="Convert a PDF to MusicXML using Audiveris.")
    pdf_parser.add_argument("pdf_path", type=Path, help="Path to the input PDF")
    pdf_parser.add_argument("--out-dir", type=Path, default=default_out_dir, help="Output directory")
    pdf_parser.add_argument("--no-rasterize", action="store_true", help="Let Audiveris read the PDF directly")
    pdf_parser.add_argument("--dpi", type=int, default=400, help="DPI for rasterization")
    pdf_parser.add_argument("--audiveris", type=str, default=None, help="Path to audiveris executable")

    # --- Sub-parser for generate_analysis_of_musicxml ---
    analyze_parser = subparsers.add_parser("generate_analysis_of_musicxml", help="Perform harmony analysis on a MusicXML file.")
    analyze_parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")
    analyze_parser.add_argument("--out-dir", default=default_out_dir, help="Output JSON file path")
    analyze_parser.add_argument("--legacy", action="store_true", help="Use the legacy analysis method")

    # --- Sub-parser for generate_simplified_musicxml ---
    simplify_parser = subparsers.add_parser("generate_simplified_musicxml", help="Generate a simplified version of the piece in a given MusicXML file (as a MusicXML file).")
    # TODO: Add --out-dir option to specify output directory
    # simplify_parser.add_argument("--out-dir", default=default_out_dir, help="Output directory")
    simplify_parser.add_argument("musicxml_path", help="Path to the original MusicXML or MXL file")
    simplify_parser.add_argument("--manual", action="store_true", help="Generate manual prompt files for review, but do not call the AI API")
    # TODO: Change default to True after issuue with GPT-5 and agents is resolved
    simplify_parser.add_argument("--use-agent", action="store_true", default=False, help="Use the OpenAI API with an agent")
    simplify_parser.add_argument("--run-model-response-in-background", default=True, action="store_true", help="Run the model response in the background")

    # --- Sub-parser for convert_musicxml_to_pdf ---
    convert_parser = subparsers.add_parser("convert_musicxml_to_pdf", help="Convert a MusicXML file to PDF.")
    convert_parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")
    convert_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PDF files.")
    # TODO: Lilipond output isn't as good as MuseScore
    convert_parser.add_argument("--convert-with-lilypond", action="store_true", default=False, help="Use LilyPond to convert to PDF (default: True)")
    convert_parser.add_argument("--convert-with-musescore", action="store_true", default=True, help="Use MuseScore to convert to PDF (default: True)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Ensure log directory exists, then configure logging to both console and file
    fs_utils.ensure_dir(Path(args.log_file).parent)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(args.log_file, encoding="utf-8"),
        ],
    )

    if args.command == "convert_pdf_to_musicxml":
        convert_pdf_to_musicxml.convert_pdf_to_musicxml(
            pdf_path=args.pdf_path,
            out_dir=args.out_dir,
            prefer_rasterize=not args.no_rasterize,
            dpi=args.dpi,
            audiveris_path=args.audiveris,
        )

    elif args.command == "generate_analysis_of_musicxml":
        # TODO: Remove legacy option after verifying new analysis improvements
        if args.legacy:
            generate_legacy_analysis_of_musicxml.generate_legacy_analysis_of_musicxml(args.musicxml_path)
        else:
            generate_analysis_of_musicxml.generate_analysis_of_musicxml(args.musicxml_path, out_dir=args.out_dir)

    elif args.command == "generate_simplified_musicxml":
        if args.manual:
            generate_simplified_musicxml.generate_chatgpt_prompts_for_simplified_musicxml(args.musicxml_path)
        else:
            generate_simplified_musicxml.generate_simplified_musicxml(args.musicxml_path, args.use_agent, args.run_model_response_in_background)

    elif args.command == "convert_musicxml_to_pdf":
        convert_musicxml_to_pdf.convert_musicxml_to_pdf(
            args.musicxml_path, convert_with_lilypond=args.convert_with_lilypond, convert_with_musescore=args.convert_with_musescore, overwrite=args.overwrite
        )


if __name__ == "__main__":
    main()
