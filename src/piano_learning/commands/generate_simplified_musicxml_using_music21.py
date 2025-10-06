#!/usr/bin/env python3
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from music21 import analysis
from music21 import chord
from music21 import converter
from music21 import duration
from music21 import meter
from music21 import note
from music21 import stream

logger = logging.getLogger(__name__)

def ql(e) -> float:
    try:
        return float(e.quarterLength)
    except Exception:
        return 0.0


def reduce_left_hand_part_to_chords(
    lh_part: stream.Part,
    window: Literal["beat", "measure"] = "beat",
) -> stream.Part:
    """
    Reduce an arpeggiated/stirred LH part to block chords.

    Strategy:
      1) Try music21.analysis reduction (ChordReducer / reduceChords) if present.
      2) Fallback: aggregate notes per time window (beat or measure) into a chord at the
         window start with duration equal to the window length.

    Returns a new Part; the original is not modified.
    """
    # 1) Try music21's analysis reducer if available
    try:
        # Prefer analysis.reduction module if present
        try:
            from music21.analysis import reduction as m21reduction  # type: ignore
        except Exception:
            m21reduction = None

        if m21reduction is not None:
            # Try ChordReducer first
            if hasattr(m21reduction, "ChordReducer"):
                try:
                    cr = m21reduction.ChordReducer(lh_part)  # type: ignore[attr-defined]
                    reduced = cr.reduceChords()  # type: ignore[call-arg]
                    if isinstance(reduced, stream.Part):
                        return reduced
                except Exception:
                    pass
            # Then try a module-level function reduceChords if exposed
            if hasattr(m21reduction, "reduceChords"):
                try:
                    reduced = m21reduction.reduceChords(lh_part)  # type: ignore[attr-defined]
                    if isinstance(reduced, stream.Part):
                        return reduced
                except Exception:
                    pass
        # Some installs expose analysis.reduceChords directly
        if hasattr(analysis, "reduceChords"):
            try:
                reduced = analysis.reduceChords(lh_part)  # type: ignore[attr-defined]
                if isinstance(reduced, stream.Part):
                    return reduced
            except Exception:
                pass
    except Exception:
        # Swallow and continue to fallback
        pass

    # 2) Fallback: window-based aggregation (beat or measure)
    out = stream.Part()
    out.id = lh_part.id
    out.partName = lh_part.partName or "LH (reduced)"

    measures = list(lh_part.getElementsByClass(stream.Measure))

    for m in measures:
        m_out = stream.Measure(number=m.number)
        # Copy local time signature if there is one
        if m.timeSignature:
            m_out.timeSignature = m.timeSignature

        ts = m.timeSignature or meter.TimeSignature("4/4")
        bar_q = float(ts.barDuration.quarterLength)
        beat_len = bar_q / max(1, ts.beatCount)

        # Build windows in local (measure) time
        if window == "measure":
            windows = [(0.0, bar_q)]
        else:
            # Beat windows
            n_beats = int(round(bar_q / beat_len))
            windows = [(i * beat_len, min((i + 1) * beat_len, bar_q)) for i in range(n_beats)]

        # Collect notes per window and emit a block chord at window start
        # Expand chords to their member notes
        measure_notes: list[note.Note] = []
        for el in m.flatten().getElementsByClass([note.Note, chord.Chord]):
            if isinstance(el, note.Note):
                if ql(el) > 0:
                    measure_notes.append(el)
            else:
                for nn in el.notes:
                    if ql(nn) > 0:
                        # Place a lightweight clone at the chord's offset
                        try:
                            nn2 = nn.clone()
                        except Exception:
                            nn2 = note.Note(nn.pitch)
                            nn2.duration.quarterLength = ql(nn)
                        nn2.offset = float(el.offset)
                        measure_notes.append(nn2)

        for ws, we in windows:
            # Notes that start in [ws, we)
            bucket = [n for n in measure_notes if ws <= float(n.offset) < we]
            if not bucket:
                continue

            # Keep the lowest instance per pitch class to avoid heavy duplications
            by_pc: dict[int, note.Note] = {}
            for n in bucket:
                pc = n.pitch.pitchClass
                if pc not in by_pc or n.pitch.midi < by_pc[pc].pitch.midi:
                    by_pc[pc] = n

            pitches = [n.pitch for n in sorted(by_pc.values(), key=lambda x: x.pitch.midi)]
            dur = max(we - ws, 0.0)
            if len(pitches) == 1:
                el_out = note.Note(pitches[0])
            else:
                el_out = chord.Chord(pitches)
            el_out.duration = duration.Duration(dur if dur > 0 else beat_len)
            # Insert at window start in the measure's local time
            m_out.insert(ws, el_out)

        out.append(m_out)

    return out

def reduce_left_hand_in_score_to_chords(
    s: stream.Score,
    window: Literal["beat", "measure"] = "beat",
) -> stream.Score:
    """
    Return the same Score with the last part (assumed LH) reduced to block chords in-place.
    Only LH measures are modified; RH and other parts are preserved.
    """
    if not s.parts:
        return s

    lh_part = s.parts[-1]
    reduced_lh = reduce_left_hand_part_to_chords(lh_part, window=window)

    # Replace contents of each LH measure with reduced chords while preserving measure containers
    orig_measures = list(lh_part.getElementsByClass(stream.Measure))
    reduced_measures = list(reduced_lh.getElementsByClass(stream.Measure))
    reduced_by_number = {m.number: m for m in reduced_measures}

    for m in orig_measures:
        rm = reduced_by_number.get(m.number)
        if rm is None:
            continue

        # Clear only musical events; keep measure-level attributes (TS, KS, clefs, barlines)
        for el in list(m.notesAndRests):
            try:
                m.remove(el)
            except Exception:
                pass

        # Insert reduced notes/chords at original local offsets
        for el in rm.getElementsByClass([note.Note, chord.Chord, note.Rest]):
            try:
                el2 = el.clone()
            except Exception:
                el2 = el
            m.insert(float(el.offset), el2)

    return s

def generate_simplified_musicxml_using_music21(musicxml_path: str, out_dir: str = ".") -> str | None:
    """
    Parse MusicXML, simplify the left hand to block chords, and write a new MusicXML.
    """
    s = converter.parse(musicxml_path)

    # Reduce LH to block chords
    s_reduced = reduce_left_hand_in_score_to_chords(s, window="beat")

    # Ensure output dir exists and write simplified MusicXML
    basename = Path(musicxml_path).stem
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(out_dir) / f"{basename}_simplified.musicxml"
    s_reduced.write("musicxml", fp=str(out_path))
    logger.info(f"Wrote simplified MusicXML to {out_path} using music21.")
    return str(out_path)
