#!/usr/bin/env python3
import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.commands import analyze_musicxml
from src.commands import convert_musicxml_to_pdf
from src.commands import convert_pdf_to_musicxml

logger = logging.getLogger(__name__)



def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Process sheet music files: analyze harmony, convert to PDF, or process PDFs.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Sub-parser for convert_pdf_to_musicxml ---
    pdf_parser = subparsers.add_parser("convert_pdf_to_musicxml", help="Convert a PDF to MusicXML using Audiveris.")
    pdf_parser.add_argument("pdf_path", type=Path, help="Path to the input PDF")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    default_out_dir = Path(f"./user/output-{timestamp}")
    pdf_parser.add_argument("--out", type=Path, default=default_out_dir, help="Output directory")
    pdf_parser.add_argument("--no-rasterize", action="store_true", help="Let Audiveris read the PDF directly")
    pdf_parser.add_argument("--dpi", type=int, default=400, help="DPI for rasterization")
    pdf_parser.add_argument("--audiveris", type=str, default=None, help="Path to audiveris executable")

    # --- Sub-parser for analyze_musicxml ---
    analyze_parser = subparsers.add_parser("analyze_musicxml", help="Perform harmony analysis on a MusicXML file.")
    analyze_parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")

    # --- Sub-parser for convert_musicxml_to_pdf ---
    convert_parser = subparsers.add_parser("convert_musicxml_to_pdf", help="Convert a MusicXML file to PDF.")
    convert_parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")
    convert_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PDF files.")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if args.command == "convert_pdf_to_musicxml":
        convert_pdf_to_musicxml.convert_pdf_to_musicxml(
            pdf_path=args.pdf_path,
            out_dir=args.out,
            prefer_rasterize=not args.no_rasterize,
            dpi=args.dpi,
            audiveris_path=args.audiveris,
        )

    elif args.command == "analyze_musicxml":
        analyze_musicxml.analyze_musicxml(args.musicxml_path)

    elif args.command == "convert_musicxml_to_pdf":
        convert_musicxml_to_pdf.convert_musicxml_to_pdf(args.musicxml_path, args.overwrite)


if __name__ == "__main__":
    main()
