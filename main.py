#!/usr/bin/env python3
import argparse
import logging
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Dict
from typing import List

from music21 import roman
from music21 import stream

import lilypond
import musescore
import score_utils

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process MusicXML files: analyze harmony and/or convert to PDF.")
    parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")
    parser.add_argument("--analyze", action="store_true", help="Perform harmony analysis.")
    parser.add_argument("--convert", action="store_true", help="Convert to PDF using available backends.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PDF files if converting.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if not args.analyze and not args.convert:
        logger.warning("Neither --analyze nor --convert specified. Nothing to do.")
        exit(0)

    if args.analyze:
        score = score_utils.load_score(args.musicxml_path)
        analysis = analyze_harmony(score)
        logger.info(analysis)

    if args.convert:
        outputs = convert_musicxml_to_pdfs(args.musicxml_path, overwrite=args.overwrite)
        for backend, path in outputs.items():
            logger.info(f"✅ The PDF can be found in: {backend} → {path}")
