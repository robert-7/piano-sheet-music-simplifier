#!/usr/bin/env python3
import argparse
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.piano_learning.utils import fs_utils

try:
    import dotenv
except ImportError:  # pragma: no cover - exercised indirectly in lightweight environments
    dotenv = None

logger = logging.getLogger(__name__)

SIMPLIFIER_MUSIC21 = "music21"
SIMPLIFIER_OPENAI = "openai"
DEFAULT_LOG_LEVEL = "INFO"

if dotenv is not None:
    dotenv.load_dotenv(dotenv_path=dotenv.find_dotenv(usecwd=True), override=False)


def add_simplifier_args(parser: argparse.ArgumentParser, *, include_manual: bool) -> None:
    """
    Adds simplifier-selection arguments to a sub-command.
    """
    parser.add_argument(
        "--simplifier",
        choices=[SIMPLIFIER_MUSIC21, SIMPLIFIER_OPENAI],
        default=SIMPLIFIER_MUSIC21,
        help="Which simplifier backend to use (default: music21).",
    )
    if include_manual:
        parser.add_argument(
            "--manual",
            action="store_true",
            help="Generate OpenAI prompt files only; requires --simplifier openai.",
        )
    parser.add_argument(
        "--use-agent",
        action="store_true",
        default=False,
        help=(
            "Use the experimental OpenAI Agents SDK when --simplifier=openai. "
            "The default OpenAI path uses the Responses API in background mode."
        ),
    )
    # Backward-compatible alias for older command examples.
    parser.add_argument("--music21", dest="legacy_music21", action="store_true", help=argparse.SUPPRESS)
    # Backward-compatible no-op: OpenAI uses background mode unless --use-agent is set.
    parser.add_argument(
        "--run-model-response-in-background",
        dest="legacy_background_mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )


def resolve_simplifier(args: argparse.Namespace) -> str:
    """
    Resolves the simplifier backend, honoring the deprecated --music21 flag.
    """
    if getattr(args, "legacy_music21", False):
        return SIMPLIFIER_MUSIC21
    return getattr(args, "simplifier", SIMPLIFIER_MUSIC21)


def validate_simplifier_args(args: argparse.Namespace) -> None:
    """
    Validates the selected simplifier and related flags.
    """
    simplifier = resolve_simplifier(args)
    if getattr(args, "manual", False) and simplifier != SIMPLIFIER_OPENAI:
        raise ValueError("--manual requires --simplifier openai.")
    if getattr(args, "use_agent", False) and simplifier != SIMPLIFIER_OPENAI:
        raise ValueError("--use-agent requires --simplifier openai.")


def resolve_log_level() -> int:
    """
    Resolves the configured log level from LOG_LEVEL in the environment or .env.
    """
    raw_value = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper()
    level = logging.getLevelName(raw_value)
    if not isinstance(level, int):
        raise ValueError(
            f"Invalid LOG_LEVEL={raw_value!r}. Expected one of DEBUG, INFO, WARNING, ERROR, or CRITICAL."
        )
    return level


def log_generate_simplified_pdf_context(args: argparse.Namespace) -> None:
    """
    Logs the raw and resolved arguments used by generate_simplified_pdf.
    """
    simplifier = resolve_simplifier(args)
    input_source = "pdf" if args.pdf_path else "musicxml"
    openai_execution_mode = "disabled"
    if simplifier == SIMPLIFIER_OPENAI:
        openai_execution_mode = "agent" if args.use_agent else "responses_background"

    logger.debug(
        "generate_simplified_pdf raw args: pdf_path=%s, musicxml_path=%s, simplifier=%s, "
        "use_agent=%s, legacy_music21=%s, legacy_background_mode=%s, out_dir=%s",
        args.pdf_path,
        args.musicxml_path,
        getattr(args, "simplifier", None),
        args.use_agent,
        getattr(args, "legacy_music21", False),
        getattr(args, "legacy_background_mode", False),
        args.out_dir,
    )
    logger.debug(
        "generate_simplified_pdf resolved context: input_source=%s, resolved_simplifier=%s, "
        "openai_execution_mode=%s",
        input_source,
        simplifier,
        openai_execution_mode,
    )


def run_simplification_backend(
    musicxml_path: str | Path,
    out_dir: Path,
    simplifier: str,
    *,
    use_agent: bool = False,
) -> Optional[str]:
    """
    Runs the selected simplifier backend and returns the generated MusicXML path.
    """
    if simplifier == SIMPLIFIER_MUSIC21:
        from src.piano_learning.commands import generate_simplified_musicxml_using_music21

        logger.info("Using simplifier backend: music21")
        return generate_simplified_musicxml_using_music21.generate_simplified_musicxml_using_music21(
            musicxml_path,
            out_dir,
        )

    from src.piano_learning.commands import generate_simplified_musicxml_using_ai

    if use_agent:
        logger.info("Using simplifier backend: openai (experimental Agents SDK)")
    else:
        logger.info("Using simplifier backend: openai (Responses API background mode)")

    return generate_simplified_musicxml_using_ai.generate_simplified_musicxml(
        musicxml_path,
        out_dir,
        use_agent=use_agent,
    )


def build_parser() -> argparse.ArgumentParser:
    """
    Builds the command-line argument parser.

    This parser provides sub-commands for processing piano music files, including:
    - Converting PDFs to MusicXML
    - Analyzing MusicXML files
    - Generating simplified MusicXML files
    - Converting MusicXML to PDF

    Each sub-command expects input files from 'user/input/' and writes outputs to a date-stamped
    directory under 'user/output/*/'.
    External tools (e.g., Audiveris, LilyPond, MuseScore) are invoked as needed.

    See README.md for usage examples and setup instructions.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    default_out_dir = Path(f"./user/output/{timestamp}")

    # Create the top-level parser with sub-commands
    parser = argparse.ArgumentParser(
        description="Process sheet music files: analyze harmony, convert to PDF, or process PDFs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")
    parser.add_argument("--out-dir", type=Path, default=default_out_dir, help="Path to the output directory.")

    # --- Sub-parser for generate_simplified_pdf ---
    pdf_simplifier_parser = subparsers.add_parser("generate_simplified_pdf", help="Simplify a PDF file.")
    pdf_simplifier_parser.add_argument("--pdf_path", type=Path, help="Path to the input PDF")
    pdf_simplifier_parser.add_argument("--musicxml_path", type=Path, help="Path to the input MusicXML")
    add_simplifier_args(pdf_simplifier_parser, include_manual=False)

    # --- Sub-parser for convert_pdf_to_musicxml ---
    pdf_parser = subparsers.add_parser("convert_pdf_to_musicxml", help="Convert a PDF to MusicXML using Audiveris.")
    pdf_parser.add_argument("pdf_path", type=Path, help="Path to the input PDF")
    pdf_parser.add_argument("--no-rasterize", action="store_true", help="Let Audiveris read the PDF directly")
    pdf_parser.add_argument("--dpi", type=int, default=400, help="DPI for rasterization")

    # --- Sub-parser for generate_analysis_of_musicxml ---
    analyze_parser = subparsers.add_parser(
        "generate_analysis_of_musicxml",
        help="Perform harmony analysis on a MusicXML file.",
    )
    analyze_parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")

    # --- Sub-parser for generate_simplified_musicxml ---
    simplify_parser = subparsers.add_parser(
        "generate_simplified_musicxml",
        help="Generate a simplified version of the piece in a given MusicXML file (as a MusicXML file).",
    )
    simplify_parser.add_argument("musicxml_path", help="Path to the original MusicXML or MXL file")
    add_simplifier_args(simplify_parser, include_manual=True)

    # --- Sub-parser for convert_musicxml_to_pdf ---
    convert_parser = subparsers.add_parser("convert_musicxml_to_pdf", help="Convert a MusicXML file to PDF.")
    convert_parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")
    convert_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PDF files.")
    convert_parser.add_argument(
        "--convert-with-lilypond",
        action="store_true",
        default=False,
        help="Use LilyPond to convert to PDF (default: False)",
    )
    convert_parser.add_argument(
        "--convert-with-musescore",
        action="store_true",
        default=True,
        help="Use MuseScore to convert to PDF (default: True)",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        validate_simplifier_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        log_level = resolve_log_level()
    except ValueError as exc:
        parser.error(str(exc))

    # Ensure log directory exists, then configure logging to both console and file
    fs_utils.ensure_dir(Path(args.out_dir))
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(args.out_dir / "piano_learning.log", encoding="utf-8"),
        ],
    )
    logger.info("Logging initialized at level: %s", logging.getLevelName(log_level))

    if args.command == "generate_simplified_pdf":
        out_dir = args.out_dir
        try:
            log_generate_simplified_pdf_context(args)
            if not args.pdf_path and not args.musicxml_path:
                logger.error("Either --pdf_path or --musicxml_path must be provided.")
                exit(1)
            if args.pdf_path:
                from src.piano_learning.commands import convert_pdf_to_musicxml

                logger.info("Using PDF for MusicXML conversion...")
                musicxml_path = convert_pdf_to_musicxml.convert_pdf_to_musicxml(args.pdf_path, out_dir, True, False)
                if not musicxml_path:
                    logger.error(f"Error converting PDF {args.pdf_path} to MusicXML. Logs can be found in {out_dir}.")
                    exit(1)
            else:
                logger.info("Skipping PDF to MusicXML conversion...")
                musicxml_path = args.musicxml_path

            simplifier = resolve_simplifier(args)
            simplified_musicxml_path = run_simplification_backend(
                musicxml_path,
                out_dir=out_dir,
                simplifier=simplifier,
                use_agent=args.use_agent,
            )
            if not simplified_musicxml_path:
                logger.error(f"Error generating simplified MusicXML from {musicxml_path}. Logs can be found in {out_dir}.")
                exit(1)
            from src.piano_learning.commands import convert_musicxml_to_pdf

            outputs = convert_musicxml_to_pdf.convert_musicxml_to_pdf(
                simplified_musicxml_path,
                out_dir=out_dir,
                convert_with_lilypond=False,
                convert_with_musescore=True,
                overwrite=True,
            )
            if not outputs:
                logger.error(f"Error generating PDFs from {simplified_musicxml_path}. Logs can be found in {out_dir}.")
                exit(1)
        except Exception as e:
            logger.error(f"Error processing {args.pdf_path}. Logs can be found in {out_dir}: {e}")

    elif args.command == "convert_pdf_to_musicxml":
        from src.piano_learning.commands import convert_pdf_to_musicxml

        convert_pdf_to_musicxml.convert_pdf_to_musicxml(args.pdf_path, args.out_dir, not args.no_rasterize, args.dpi)

    elif args.command == "generate_analysis_of_musicxml":
        from src.piano_learning.commands import generate_analysis_of_musicxml

        generate_analysis_of_musicxml.generate_analysis_of_musicxml(args.musicxml_path, out_dir=args.out_dir)

    elif args.command == "generate_simplified_musicxml":
        simplifier = resolve_simplifier(args)
        if args.manual:
            from src.piano_learning.commands import generate_simplified_musicxml_using_ai

            generate_simplified_musicxml_using_ai.generate_chatgpt_prompts_for_simplified_musicxml(
                args.musicxml_path,
                args.out_dir,
            )
        else:
            run_simplification_backend(
                args.musicxml_path,
                out_dir=args.out_dir,
                simplifier=simplifier,
                use_agent=args.use_agent,
            )

    elif args.command == "convert_musicxml_to_pdf":
        from src.piano_learning.commands import convert_musicxml_to_pdf

        convert_musicxml_to_pdf.convert_musicxml_to_pdf(
            args.musicxml_path,
            args.out_dir,
            convert_with_lilypond=args.convert_with_lilypond,
            convert_with_musescore=args.convert_with_musescore,
            overwrite=args.overwrite,
        )


if __name__ == "__main__":
    main()
