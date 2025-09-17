#!/usr/bin/env python3
import argparse
import logging
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import List

from music21 import roman
from music21 import stream

from src import audiveris
from src import lilypond
from src import musescore
from src import score_utils

logger = logging.getLogger(__name__)


@dataclass
class HarmonyAnalysis:
    estimated_key: str = ""
    roman_figures: List[str] = field(default_factory=list)
    chord_qualities: List[str] = field(default_factory=list)
    pitch_classes: List[int] = field(default_factory=list)

    def __str__(self):
        lines = [
            f"Estimated Key = {self.estimated_key}",
            f"Roman Figures (collapsed) = {self.roman_figures[:40]}{' ...' if len(self.roman_figures) > 40 else ''}",
            f"Chord Qualities = {self.chord_qualities}",
            f"Pitch Classes = {self.pitch_classes}",
        ]
        return "\n".join(lines)

def analyze_harmony(score: stream.Stream,
                    *,
                    concert_pitch: bool = True,
                    min_notes_per_chord: int = 2,
                    collapse_repeats: bool = True) -> HarmonyAnalysis:
    """Estimate key; extract roman numerals, chord qualities, and pitch classes.
    Designed to degrade gracefully on monophonic lines."""
    analysis = HarmonyAnalysis()

    s = score.toSoundingPitch() if concert_pitch else score
    ks = s.analyze('key')
    analysis.estimated_key = str(ks)

    chordified = s.chordify()
    chords = chordified.recurse().getElementsByClass('Chord')

    roman_figures = []
    chord_qualities = set()
    pitch_classes = set()

    for c in chords:
        pcs = set(c.pitchClasses)
        if len(pcs) < min_notes_per_chord:
            # Treat single-note “chords” as melody; still collect pitch classes.
            pitch_classes.update(pcs)
            continue

        rn = roman.romanNumeralFromChord(c, ks)
        roman_figures.append(rn.figure)
        chord_qualities.add(c.commonName or c.quality)  # commonName is friendly when it exists
        pitch_classes.update(pcs)

    if collapse_repeats:
        roman_figures = [x for i, x in enumerate(roman_figures) if i == 0 or x != roman_figures[i-1]]

    analysis.roman_figures = roman_figures
    analysis.chord_qualities = sorted(chord_qualities)
    analysis.pitch_classes = sorted(pitch_classes)
    return analysis


def convert_musicxml_to_pdfs(musicxml_path: str, *, overwrite: bool = False) -> Dict[str, Path]:
    """
    Render a MusicXML/MXL file to PDF with both LilyPond and MuseScore (when available).
    Output files are <stem>.LilyPond.pdf and <stem>.MuseScore.pdf in the same directory.

    Returns: dict { 'LilyPond': Path, 'MuseScore': Path } for the backends that succeeded.
    Raises:  FileNotFoundError if input doesn't exist; RuntimeError if no backend could produce a PDF.
    """
    results: Dict[str, Path] = {}
    errors: Dict[str, Exception] = {}

    key = "LilyPond"
    try:
        results[key] = lilypond.convert_musicxml_to_pdf(musicxml_path, overwrite=overwrite)
    except (FileNotFoundError, RuntimeError) as e:
        errors[key] = e
        logger.error(f"{key} failed: {e}")

    key = "MuseScore"
    try:
        results[key] = musescore.convert_musicxml_to_pdf(musicxml_path, overwrite=overwrite)
    except (FileNotFoundError, RuntimeError) as e:
        errors[key] = e
        logger.error(f"{key} failed: {e}")

    if not results:
        msg = ["Could not generate a PDF with LilyPond or MuseScore."]
        for k, e in errors.items():
            msg.append(f"{k} error: {e}")
        raise RuntimeError("\n".join(msg))

    return results


def main():
    parser = argparse.ArgumentParser(description="Process sheet music files: analyze harmony, convert to PDF, or process PDFs.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Sub-parser for convert_pdf_to_musicxml ---
    pdf_parser = subparsers.add_parser("convert_pdf_to_musicxml", help="Convert a PDF to MusicXML using Audiveris.")
    pdf_parser.add_argument("pdf_path", type=Path, help="Path to the input PDF")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
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

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if args.command == "convert_pdf_to_musicxml":
        result = audiveris.convert_pdf_to_musicxml(
            pdf_path=args.pdf_path,
            out_dir=args.out,
            prefer_rasterize=not args.no_rasterize,
            dpi=args.dpi,
            audiveris_path=args.audiveris,
        )
        logger.info(f"\nAudiveris outputs ({len(result.outputs)}):")
        for p in result.outputs:
            logger.info(f"  {p}")
        logger.info(f"\nLog: {result.log_path}")

    elif args.command == "analyze_musicxml":
        score = score_utils.load_score(args.musicxml_path)
        analysis = analyze_harmony(score)
        logger.info(analysis)

    elif args.command == "convert_musicxml_to_pdf":
        outputs = convert_musicxml_to_pdfs(args.musicxml_path, overwrite=args.overwrite)
        for backend, path in outputs.items():
            logger.info(f"✅ The PDF can be found in: {backend} → {path}")


if __name__ == "__main__":
    main()
