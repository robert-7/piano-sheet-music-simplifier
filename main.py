#!/usr/bin/env python3
import argparse
import shutil
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Dict
from typing import List

from music21 import converter
from music21 import environment
from music21 import roman
from music21 import stream

BACKEND_LILYPOND = "LilyPond"
BACKEND_MUSESCORE = "MuseScore"

def _detect_lilypond() -> str | None:
    """
    Detect the LilyPond executable on the system.

    Returns:
        str | None: The path to the LilyPond executable if found, otherwise None.
    """
    p = shutil.which("lilypond")
    if p:
        return p
    # common fallback on Ubuntu
    if Path("/usr/bin/lilypond").exists():
        return "/usr/bin/lilypond"
    return None

def _detect_musescore() -> str | None:
    """
    Detect the MuseScore executable on the system, preferring a Flatpak wrapper if present.

    Returns:
        str | None: The path to the MuseScore executable if found, otherwise None.
    """
    # Prefer your Flatpak wrapper if you created it:
    wrapper = Path("/usr/local/bin/musescore")
    if wrapper.exists():
        return str(wrapper)
    # Otherwise, try native binaries
    for name in ("musescore", "mscore", "musescore3"):
        p = shutil.which(name)
        if p:
            return p
    return None

def _needs_build(src: Path, dst: Path, overwrite: bool) -> bool:
    """
    Determine if a destination file needs to be rebuilt based on its existence,
    modification time, or an explicit overwrite flag.

    Args:
        src (Path): The source file path.
        dst (Path): The destination file path.
        overwrite (bool): Whether to force rebuilding the destination file.

    Returns:
        bool: True if the destination file needs to be rebuilt, False otherwise.
    """
    return overwrite or (not dst.exists()) or (dst.stat().st_mtime < src.stat().st_mtime)

def load_score(path: str) -> stream.Score:
    """Load a MusicXML score from the given path, raising if not found or invalid."""
    try:
        score = converter.parse(path)
        print(f"Loaded score from '{path}' with {len(score.parts)} parts.")
        return score
    except Exception as e:
        raise Exception(f"Failed to load score from '{path}': {e}")

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
    src = Path(musicxml_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)

    out_dir, stem = src.parent, src.stem
    results: Dict[str, Path] = {}
    errors: Dict[str, Exception] = {}
    us = environment.UserSettings()

    # --- LilyPond ---
    lily = _detect_lilypond()
    if lily:
        try:
            us["lilypondPath"] = lily
            dst = out_dir / f"{stem}.LilyPond.pdf"
            if _needs_build(src, dst, overwrite):
                score = converter.parse(str(src))
                score.write("lily.pdf", fp=str(dst))
            results[BACKEND_LILYPOND] = dst
        except Exception as e:
            errors[BACKEND_LILYPOND] = e

    # --- MuseScore (MusicXML backend) ---
    mscore = _detect_musescore()
    if mscore:
        try:
            us["musicxmlPath"] = mscore
            us['musescoreDirectPNGPath'] = mscore
            dst = out_dir / f"{stem}.MuseScore.pdf"
            if _needs_build(src, dst, overwrite):
                score = converter.parse(str(src))
                score.write("musicxml.pdf", fp=str(dst))
            results[BACKEND_MUSESCORE] = dst
        except Exception as e:
            errors[BACKEND_MUSESCORE] = e

    if not results:
        msg = ["Could not generate a PDF with LilyPond or MuseScore."]
        for k, e in errors.items():
            msg.append(f"{k} error: {e}")
        raise RuntimeError("\n".join(msg))

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert MusicXML to PDF using LilyPond and MuseScore.")
    parser.add_argument("musicxml_path", help="Path to the MusicXML or MXL file")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PDF files")
    args = parser.parse_args()

    score = load_score(args.musicxml_path)
    analysis = analyze_harmony(score)
    print(analysis)

    outputs = convert_musicxml_to_pdfs(args.musicxml_path, overwrite=args.overwrite)
    for backend, path in outputs.items():
        print(f"✅ The PDF can be found in: {backend} → {path}")
