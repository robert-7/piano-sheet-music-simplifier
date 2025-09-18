import logging
from dataclasses import dataclass
from dataclasses import field
from typing import List

from music21 import roman
from music21 import stream

from src.utils import score_utils

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


def analyze_harmony(
    score: stream.Stream,
    *,
    concert_pitch: bool = True,
    min_notes_per_chord: int = 2,
    collapse_repeats: bool = True,
) -> HarmonyAnalysis:
    """Estimate key; extract roman numerals, chord qualities, and pitch classes.
    Designed to degrade gracefully on monophonic lines."""
    analysis = HarmonyAnalysis()

    s = score.toSoundingPitch() if concert_pitch else score
    ks = s.analyze("key")
    analysis.estimated_key = str(ks)

    chordified = s.chordify()
    chords = chordified.recurse().getElementsByClass("Chord")

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
        chord_qualities.add(
            c.commonName or c.quality
        )  # commonName is friendly when it exists
        pitch_classes.update(pcs)

    if collapse_repeats:
        roman_figures = [
            x for i, x in enumerate(roman_figures) if i == 0 or x != roman_figures[i - 1]
        ]

    analysis.roman_figures = roman_figures
    analysis.chord_qualities = sorted(chord_qualities)
    analysis.pitch_classes = sorted(pitch_classes)
    return analysis


def generate_legacy_analysis_of_musicxml(musicxml_path: str):
    score = score_utils.load_score(musicxml_path)
    analysis = analyze_harmony(score)
    logger.info(analysis)
