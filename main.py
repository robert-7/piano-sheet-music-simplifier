#!/usr/bin/env python3
import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.piano_learning.commands import convert_musicxml_to_pdf
from src.piano_learning.commands import convert_pdf_to_musicxml
from src.piano_learning.commands import generate_analysis_of_musicxml
from src.piano_learning.commands import generate_simplified_musicxml_using_ai
from src.piano_learning.commands import generate_simplified_musicxml_using_music21
from src.piano_learning.utils import fs_utils

logger = logging.getLogger(__name__)



def build_parser() -> argparse.ArgumentParser:
    """
    Builds the command-line argument parser.

    This parser provides sub-commands for processing piano music files, including:
    - Converting PDFs to MusicXML
    - Analyzing MusicXML files
    - Generating simplified MusicXML files
    - Converting MusicXML to PDF

    Each sub-command expects input files from 'user/input/' and writes outputs to a date-stamped directory under 'user/output/*/'.
    External tools (e.g., Audiveris, LilyPond, MuseScore) are invoked as needed.

    See README.md for usage examples and setup instructions.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    default_out_dir = Path(f"./user/output/{timestamp}")

    # Create the top-level parser with sub-commands
    parser = argparse.ArgumentParser(description="Process sheet music files: analyze harmony, convert to PDF, or process PDFs.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")
    parser.add_argument("--out-dir", type=Path, default=default_out_dir, help="Path to the output directory.")

    # --- Sub-parser for generate_simplified_pdf ---
    pdf_simplifier_parser = subparsers.add_parser("generate_simplified_pdf", help="Simplify a PDF file.")
    pdf_simplifier_parser.add_argument("--pdf_path", type=Path, help="Path to the input PDF")
    pdf_simplifier_parser.add_argument("--musicxml_path", type=Path, help="Path to the input MusicXML")

    # --- Sub-parser for convert_pdf_to_musicxml ---
    pdf_parser = subparsers.add_parser("convert_pdf_to_musicxml", help="Convert a PDF to MusicXML using Audiveris.")
    pdf_parser.add_argument("pdf_path", type=Path, help="Path to the input PDF")
    pdf_parser.add_argument("--no-rasterize", action="store_true", help="Let Audiveris read the PDF directly")
    pdf_parser.add_argument("--dpi", type=int, default=400, help="DPI for rasterization")

    # --- Sub-parser for generate_analysis_of_musicxml ---
    analyze_parser = subparsers.add_parser("generate_analysis_of_musicxml", help="Perform harmony analysis on a MusicXML file.")
    analyze_parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")

    # --- Sub-parser for generate_simplified_musicxml ---
    simplify_parser = subparsers.add_parser("generate_simplified_musicxml", help="Generate a simplified version of the piece in a given MusicXML file (as a MusicXML file).")
    simplify_parser.add_argument("musicxml_path", help="Path to the original MusicXML or MXL file")
    simplify_parser.add_argument("--manual", action="store_true", help="Generate manual prompt files for review, but do not call the AI API")
    simplify_parser.add_argument("--music21", action="store_true", default=True, help="Use music21 for analysis and simplification instead of AI")
    # TODO: Change default to True after issuue with GPT-5 and agents is resolved
    simplify_parser.add_argument("--use-agent", action="store_true", default=False, help="Use the OpenAI API with an agent")
    simplify_parser.add_argument("--run-model-response-in-background", default=True, action="store_true", help="Run the model response in the background")

    # --- Sub-parser for convert_musicxml_to_pdf ---
    convert_parser = subparsers.add_parser("convert_musicxml_to_pdf", help="Convert a MusicXML file to PDF.")
    convert_parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")
    convert_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PDF files.")
    # TODO: Lilipond output isn't as good as MuseScore.
    convert_parser.add_argument("--convert-with-lilypond", action="store_true", default=False, help="Use LilyPond to convert to PDF (default: True)")
    convert_parser.add_argument("--convert-with-musescore", action="store_true", default=True, help="Use MuseScore to convert to PDF (default: True)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Ensure log directory exists, then configure logging to both console and file
    fs_utils.ensure_dir(Path(args.out_dir))
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(args.out_dir / "piano_learning.log", encoding="utf-8"),
        ],
    )

    if args.command == "generate_simplified_pdf":
        out_dir = args.out_dir
        try:
            if not args.pdf_path and not args.musicxml_path:
                logger.error("Either --pdf_path or --musicxml_path must be provided.")
                exit(1)
            if args.pdf_path:
                logger.info("Using PDF for MusicXML conversion...")
                musicxml_path = convert_pdf_to_musicxml.convert_pdf_to_musicxml(args.pdf_path, out_dir, True, False)
                if not musicxml_path:
                    logger.error(f"Error converting PDF {args.pdf_path} to MusicXML. Logs can be found in {out_dir}.")
                    exit(1)
            else:
                logger.info("Skipping PDF to MusicXML conversion...")
                musicxml_path = args.musicxml_path
            # Simplify MusicXML using music21 for now
            logger.info("Generating simplified MusicXML using music21...")
            simplified_musicxml_path = generate_simplified_musicxml_using_music21.generate_simplified_musicxml_using_music21(musicxml_path, out_dir=out_dir)
            if not simplified_musicxml_path:
                logger.error(f"Error generating simplified MusicXML from {musicxml_path}. Logs can be found in {out_dir}.")
                exit(1)
            outputs = convert_musicxml_to_pdf.convert_musicxml_to_pdf(
                simplified_musicxml_path, out_dir=out_dir, convert_with_lilypond=False, convert_with_musescore=True, overwrite=True)
            if not outputs:
                logger.error(f"Error generating PDFs from {simplified_musicxml_path}. Logs can be found in {out_dir}.")
                exit(1)
        except Exception as e:
            logger.error(f"Error processing {args.pdf_path}. Logs can be found in {out_dir}: {e}")

    elif args.command == "convert_pdf_to_musicxml":
        convert_pdf_to_musicxml.convert_pdf_to_musicxml(args.pdf_path, args.out_dir, not args.no_rasterize, args.dpi)

    elif args.command == "generate_analysis_of_musicxml":
        generate_analysis_of_musicxml.generate_analysis_of_musicxml(args.musicxml_path, out_dir=args.out_dir)

    elif args.command == "generate_simplified_musicxml":
        if args.manual:
            generate_simplified_musicxml_using_ai.generate_chatgpt_prompts_for_simplified_musicxml(args.musicxml_path, args.out_dir)
        else:
            if args.music21:
                logger.info("Using music21 for simplification...")
                generate_simplified_musicxml_using_music21.generate_simplified_musicxml_using_music21(args.musicxml_path, args.out_dir)
            else:
                logger.info("Using OpenAI for simplification...")
                generate_simplified_musicxml_using_ai.generate_simplified_musicxml(args.musicxml_path, args.out_dir, args.use_agent, args.run_model_response_in_background)

    elif args.command == "convert_musicxml_to_pdf":
        convert_musicxml_to_pdf.convert_musicxml_to_pdf(
            args.musicxml_path, args.out_dir,
            convert_with_lilypond=args.convert_with_lilypond, convert_with_musescore=args.convert_with_musescore, overwrite=args.overwrite
        )


if __name__ == "__main__":
    main()
