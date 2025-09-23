#!/usr/bin/env python3
"""
music21_simplify_analysis.py

Extract a structured analysis bundle from a MusicXML (or any music21-readable) score
to assist with generating simplified piano arrangements (keep RH melody exact, simplify LH).

Tested conceptually with: music21==9.7.1

Why this exists (arranger's POV)
--------------------------------
When you ask for a "simplified arrangement," you usually want to keep the *melody* and the
*harmonic intent* while reducing *technical difficulty* (especially left-hand figures).
This script computes a compact, machine-friendly summary that answers:
- What meter/tempo grid am I aligning to?
- What keys and chords are implied, and how long do they last (harmonic rhythm)?
- What is the exact melody line to preserve?
- What is the bass/registration guidance for left-hand voicing?
- What texture is the LH using now (arpeggios, alberti, block chords, octaves, etc.)?
- Which notes are non-chord tones I can safely drop in a beginner arrangement?
- Where are cadences/phrases so the simplified accompaniment can breathe naturally?

Output JSON (high-level)
------------------------
metadata      : Barline-level scaffolding (meters, tempi, pickup, repeats/voltas)
keys          : Local key areas over time (for tonicizations & RN context)
harmonies     : Beat-aligned chord summary (root/quality/inversion + Roman numeral)
melody        : Exact preserved top-line (offset, pitch, duration, ties/ornaments)
bassline      : Lowest sounding line (guides LH root/voicing & register)
textureLH     : LH texture tags per measure range (e.g., brokenArpeggio → blockable)
nctMask       : Coarse non-chord-tone flags to prune busy notes safely
ranges        : Practical pitch ranges for RH/LH (for voicing limits)
cadences      : Simple cadence hits (V→I, V→vi) to shape LH arrivals
preferences   : Defaults the downstream arranger can honor (no shortening, etc.)

Usage
-----
    python music21_simplify_analysis.py /path/to/file.musicxml --out analysis.json
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from music21 import analysis
from music21 import bar
from music21 import chord
from music21 import converter
from music21 import duration
from music21 import interval
from music21 import meter
from music21 import note
from music21 import roman
from music21 import spanner
from music21 import stream
from music21 import tempo

logger = logging.getLogger(__name__)

# -------------------------------
# Utilities
# -------------------------------

def ql(e: Any) -> float:
    """Return element quarterLength with a safe fallback (0.0 if absent)."""
    try:
        return float(e.quarterLength)
    except Exception:
        return 0.0

def elem_offset(e: Any) -> float:
    """
    Absolute offset in the score hierarchy if available; otherwise local offset.
    Offsets let us align melody/harmony/bass events on the same timeline.
    """
    try:
        return float(e.getOffsetInHierarchy(e.getContextByClass(stream.Score) or e.getContextByClass(stream.Part)))
    except Exception:
        try:
            return float(e.offset)
        except Exception:
            return 0.0

def pitch_name(n: note.Note) -> str:
    """Canonical pitch label with octave (e.g., 'D5')."""
    return n.nameWithOctave if hasattr(n, "nameWithOctave") else str(n.pitch)

def to_jsonable(obj):
    """Ensure all outputs are JSON-serializable (fallback to str for unknown types)."""
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)

# -------------------------------
# Data classes for output schema
# -------------------------------

@dataclass
class TimeSigSpan:
    """A time signature in effect starting at a given measure (e.g., 3/4 → waltz feel)."""
    mStart: int
    sig: str

@dataclass
class TempoSpan:
    """A tempo change in effect starting at a given measure (qpm = quarter-notes per minute)."""
    mStart: int
    qpm: float

@dataclass
class RepeatInfo:
    """
    Repeat/volta indicators help keep the simplified version structurally identical,
    even if we reduce the density of notes inside the repeated sections.
    """
    type: str  # 'repeatStart', 'repeatEnd', or 'volta'
    measures: list[int]

@dataclass
class Metadata:
    """Bar-grid context for aligning all reductions cleanly."""
    timeSignatures: list[TimeSigSpan]
    tempi: list[TempoSpan]
    pickupBeats: float
    repeats: list[RepeatInfo]

@dataclass
class KeyArea:
    """Local key at a measure start; supports RN analysis and cadence detection."""
    mStart: int
    localKey: str

@dataclass
class HarmonyEvent:
    """
    Beat-aligned harmony snapshot; determines chord tones vs non-chord tones and
    guides LH block-chord selection & duration (harmonic rhythm).
    """
    offset: float
    qLen: float
    root: str | None
    quality: str | None
    inversion: int | None
    rn: str | None

@dataclass
class MelodyEvent:
    """
    Exact top-line to preserve: the simplified arrangement should keep this intact.
    """
    offset: float
    pitch: str
    qLen: float
    tie: bool
    ornament: str | None

@dataclass
class BassEvent:
    """
    Lowest pitch per onset from chordified score; useful for LH root/voicing and register.
    """
    offset: float
    pitch: str
    qLen: float

@dataclass
class TextureSpan:
    """
    LH texture over a range of measures, e.g., 'brokenArpeggio' → candidate to replace with blocks.
    """
    mRange: tuple[int, int]
    pattern: str
    smallestUnit: str

@dataclass
class NCTEvent:
    """
    Non-chord-tone (NCT) mask. Coarse flags to identify notes we can usually drop safely
    (passing/neighbor/suspension-like) when simplifying accompaniment.
    """
    offset: float
    part: str
    pitch: str
    isChordTone: bool
    nctType: str | None
    keep: bool

@dataclass
class Ranges:
    """Pitch ranges per hand for ergonomic voicing constraints in the simplified LH."""
    RH: dict[str, str]
    LH: dict[str, str]

@dataclass
class Cadence:
    """Cadence touch-points to time stronger LH arrivals or pedal placements."""
    mEnd: int
    type: str
    key: str

@dataclass
class Preferences:
    """
    Downstream arranger preferences (defaults). Not analysis per se, but helps the
    generator honor musical/ergonomic constraints without re-prompting.
    """
    keepMelodyExact: bool = True
    lhStyle: str = "blockChords"
    maxLHSpan: str = "10th"
    allowOctaves: bool = True
    dropNCTs: bool = True
    keepTuplets: bool = False
    pedalPolicy: str = "cadencesOnly"
    noShortening: bool = True

# -------------------------------
# Extractors
# -------------------------------

def extract_metadata(s: stream.Score) -> Metadata:
    """
    Collect meter, tempo, pickup (if anacrusis), and repeats/voltas.

    FIX for your error:
    -------------------
    In music21, "volta" brackets are represented as spanners of type
    spanner.RepeatBracket (not bar.Volta). Attempting to access bar.Volta
    raises AttributeError on typical installs. We therefore:
      * Keep bar.Repeat for :|| and ||: (repeat barlines), and
      * Gather voltas via spanner.RepeatBracket found in the first part.
    """
    ts_map: list[TimeSigSpan] = []
    tempo_map: list[TempoSpan] = []
    repeat_info: list[RepeatInfo] = []

    # Time signatures by measure start
    for m in s.parts[0].getElementsByClass(stream.Measure):
        ts = m.timeSignature
        if ts:
            ts_map.append(TimeSigSpan(mStart=m.number, sig=ts.ratioString))

    # Tempi by measure start
    for m in s.parts[0].getElementsByClass(stream.Measure):
        tms = m.getElementsByClass(tempo.MetronomeMark)
        if tms:
            qpm = float(tms[0].number) if tms[0].number is not None else 0.0
            tempo_map.append(TempoSpan(mStart=m.number, qpm=qpm))

    # Pickup detection (anacrusis): if first bar is shorter than time-signature bar length
    pickup_beats = 0.0
    try:
        first_m = s.parts[0].measure(1)
        if first_m and first_m.timeSignature:
            expected = first_m.timeSignature.barDuration.quarterLength
            actual = sum(ql(e) for e in first_m.notesAndRests)
            if actual < expected:  # positive pickup length
                pickup_beats = expected - actual
    except Exception:
        pass

    # Repeat barlines (start/end)
    first_part = s.parts[0]
    for m in first_part.getElementsByClass(stream.Measure):
        if m.leftBarline and isinstance(m.leftBarline, bar.Repeat):
            if getattr(m.leftBarline, "direction", None) == "start":
                repeat_info.append(RepeatInfo(type="repeatStart", measures=[m.number]))
        if m.rightBarline and isinstance(m.rightBarline, bar.Repeat):
            if getattr(m.rightBarline, "direction", None) == "end":
                repeat_info.append(RepeatInfo(type="repeatEnd", measures=[m.number]))

    # Volta brackets via spanners
    # A RepeatBracket spans a set of measures; we approximate the measure numbers covered.
    for rb in first_part.recurse().getElementsByClass(spanner.RepeatBracket):
        covered_measures = []
        try:
            spanned = rb.getSpannedElements()
            for el in spanned:
                meas = el.getContextByClass(stream.Measure)
                if meas is not None and meas.number is not None:
                    covered_measures.append(int(meas.number))
        except Exception:
            pass
        if not covered_measures and hasattr(rb, "number"):
            # fallback: if we only know the number label, record the current measure if available
            m = first_part.measure(1)
            covered_measures = [m.number] if m else []
        if covered_measures:
            covered_measures = sorted(set(covered_measures))
            repeat_info.append(RepeatInfo(type="volta", measures=covered_measures))

    return Metadata(timeSignatures=ts_map, tempi=tempo_map, pickupBeats=pickup_beats, repeats=repeat_info)


def detect_key_map(s: stream.Score, window_measures: int = 4) -> list[KeyArea]:
    """
    Slide a window over measures and detect local keys.
    - Helps Roman numeral labeling remain contextually correct in tonicizations.
    - window_measures can be tuned for faster changes vs stability.
    """
    key_areas: list[KeyArea] = []
    part0 = s.parts[0]
    measures = list(part0.getElementsByClass(stream.Measure))
    n = len(measures)
    last_key_name = None
    for i in range(0, n, window_measures):
        start_m = measures[i].number
        end_idx = min(i + window_measures, n)
        seg = stream.Stream()
        for j in range(i, end_idx):
            # append actual note elements (not iterators/lists); clone to avoid moving them
            for nEl in measures[j].flatten().notes:
                try:
                    seg.append(nEl.clone())
                except Exception:
                    seg.append(nEl)
        try:
            kd = analysis.discrete.KrumhanslSchmuckler()
            k = kd.getSolution(seg)
            key_name = f"{k.tonic.name} {k.mode}"
        except Exception:
            key_name = "Unknown"
        if key_name != last_key_name:
            key_areas.append(KeyArea(mStart=start_m, localKey=key_name))
            last_key_name = key_name
    return key_areas


def describe_chord_quality(c: chord.Chord) -> tuple[str | None, int | None]:
    """
    Return a simple (quality, inversion) tuple based on triad/7th where possible.
    This is enough for deciding block-chord voicings in the LH.
    """
    try:
        if c.isTriad():
            return (c.quality, c.inversion())
        if c.isSeventh():
            return (c.quality + "7", c.inversion())
        return ("other", c.inversion())
    except Exception:
        return (None, None)


def extract_harmonies(s: stream.Score) -> list[HarmonyEvent]:
    """
    Beat-aligned harmonies using chordify, with Roman numerals in local keys.
    This drives: chord-tone detection, LH voicing choice, and harmonic rhythm.
    """
    chordified_score = s.chordify()
    # Normalize to a Stream/Part-like object; do not call removeDuplicates (may not exist)
    ch = chordified_score.parts[0] if isinstance(chordified_score, stream.Score) and chordified_score.parts else chordified_score
    events: list[HarmonyEvent] = []

    # Measure→key map for local RN; use a sane default if unknown
    key_map = detect_key_map(s)
    def key_at_measure(mno: int) -> str:
        current = "C major"
        for ka in key_map:
            if mno >= ka.mStart:
                current = ka.localKey
            else:
                break
        return current

    # One harmony per beat (coarse), taken as the richest chord onset in that beat
    analysis_stream = ch
    measures = list(analysis_stream.getElementsByClass(stream.Measure))
    for m in measures:
        ts = m.timeSignature or meter.TimeSignature("4/4")
        beat_unit = ts.barDuration.quarterLength / max(1, ts.beatCount)
        beat_buckets: dict[int, list[chord.Chord]] = {}
        for e in m.notesAndRests:
            if isinstance(e, chord.Chord):
                b = int((e.offset / beat_unit) + 1e-6)
                beat_buckets.setdefault(b, []).append(e)

        for b_idx in sorted(beat_buckets):
            cands = beat_buckets[b_idx]
            c = max(cands, key=lambda x: len(x.pitches))
            off = elem_offset(c)
            root = c.root().name if c.root() else None
            quality, inv = describe_chord_quality(c)

            rn_text = None
            try:
                lk = key_at_measure(m.number)
                tonic, mode = lk.split()
                rn_obj = roman.romanNumeralFromChord(c, keyStr=f"{tonic} {mode}")
                rn_text = rn_obj.figure
            except Exception:
                rn_text = None

            events.append(HarmonyEvent(offset=off, qLen=beat_unit, root=root, quality=quality, inversion=inv, rn=rn_text))

    # Merge consecutive identical harmonies → harmonic rhythm
    merged: list[HarmonyEvent] = []
    for ev in events:
        if merged and (ev.root, ev.quality, ev.inversion, ev.rn) == (merged[-1].root, merged[-1].quality, merged[-1].inversion, merged[-1].rn):
            merged[-1].qLen += ev.qLen
        else:
            merged.append(ev)
    return merged


def extract_melody(s: stream.Score) -> list[MelodyEvent]:
    """
    Extract a single top-line melody to preserve exactly.
    Heuristic: if there are multiple parts, assume parts[0] is RH and use its highest notes.
    """
    mel: list[MelodyEvent] = []
    rh = s.parts[0].flatten().notesAndRests if len(s.parts) >= 1 else s.flatten().notesAndRests
    for n in rh:
        if isinstance(n, note.Note):
            tie = bool(n.tie and n.tie.type in ("start", "continue", "stop"))
            orn = None
            try:
                if n.expressions:
                    orn = n.expressions[0].classes[0]
            except Exception:
                pass
            mel.append(MelodyEvent(offset=elem_offset(n), pitch=pitch_name(n), qLen=ql(n), tie=tie, ornament=orn))
        elif isinstance(n, chord.Chord):
            # Use highest note of an RH chord as the melodic head
            hn = max(n.notes, key=lambda x: x.pitch.midi)
            tie = bool(hn.tie and hn.tie.type in ("start", "continue", "stop"))
            mel.append(MelodyEvent(offset=elem_offset(hn), pitch=pitch_name(hn), qLen=ql(hn), tie=tie, ornament=None))
    return mel


def extract_bassline(s: stream.Score) -> list[BassEvent]:
    """
    Lowest sounding pitch per onset from a chordified view of the score.
    Helps choose LH roots and comfortable registration for block chords.
    """
    out: list[BassEvent] = []
    ch = s.chordify()
    for e in ch.recurse().getElementsByClass(chord.Chord):
        b = e.bass()
        if b:
            out.append(BassEvent(offset=elem_offset(e), pitch=pitch_name(b), qLen=ql(e)))
    return out


def classify_lh_texture(s: stream.Score) -> list[TextureSpan]:
    """
    Coarse LH texture classification by measure.
    Tags: 'block', 'brokenArpeggio', 'alberti', 'octaves', 'stride', 'other'.
    Used to decide where and how to replace busy figures with simpler blocks.
    """
    if len(s.parts) < 2:
        return []

    lh = s.parts[-1]  # assume last part = LH for piano scores
    spans: list[TextureSpan] = []

    def smallest_unit(measure: stream.Measure) -> str:
        min_q = 999.0
        for n in measure.notesAndRests:
            if ql(n) > 0:
                min_q = min(min_q, ql(n))
        if min_q >= 1.0:
            return "quarter"
        if min_q >= 0.5:
            return "eighth"
        if min_q >= 0.25:
            return "sixteenth"
        return "thirty-second"

    measures = list(lh.getElementsByClass(stream.Measure))
    for m in measures:
        pattern = "other"
        notes_in_m = [n for n in m.flatten().notes if isinstance(n, note.Note)]
        chords_in_m = [c for c in m.flatten().getElementsByClass(chord.Chord)]
        octaves_ratio = 0.0
        if notes_in_m:
            num_oct = sum(1 for j in range(1, len(notes_in_m))
                          if abs(interval.notesToInterval(notes_in_m[j-1], notes_in_m[j]).semitones) in (12, 24))
            octaves_ratio = num_oct / max(1, len(notes_in_m) - 1)

        if chords_in_m and len(chords_in_m) >= max(1, len(notes_in_m) // 3):
            pattern = "block"
        elif octaves_ratio > 0.5:
            pattern = "octaves"
        elif len(notes_in_m) >= 4:
            # Alberti (approx): low-high-mid-high
            mids = [n.pitch.midi for n in notes_in_m[:4]]
            if len(mids) == 4:
                rel = [mids[1] > mids[0], mids[2] < mids[1], mids[3] > mids[2]]
                if rel == [True, True, True]:
                    pattern = "alberti"
            # Broken arpeggio: mostly ascending or descending
            asc = sum(1 for j in range(1, len(notes_in_m)) if notes_in_m[j].pitch.midi > notes_in_m[j-1].pitch.midi)
            desc = sum(1 for j in range(1, len(notes_in_m)) if notes_in_m[j].pitch.midi < notes_in_m[j-1].pitch.midi)
            if max(asc, desc) >= int(0.7 * (len(notes_in_m) - 1)):
                pattern = "brokenArpeggio"

        # Stride feel: multiple large leaps + clustered chords present
        if pattern == "other" and len(notes_in_m) >= 2:
            big_leaps = sum(1 for j in range(1, len(notes_in_m))
                            if abs(notes_in_m[j].pitch.midi - notes_in_m[j-1].pitch.midi) >= 12)
            if big_leaps >= 2 and chords_in_m:
                pattern = "stride"

        spans.append(TextureSpan(mRange=(m.number, m.number), pattern=pattern, smallestUnit=smallest_unit(m)))

    # Merge adjacent identical tags for readability
    merged: list[TextureSpan] = []
    for sp in spans:
        if merged and sp.pattern == merged[-1].pattern and sp.smallestUnit == merged[-1].smallestUnit and sp.mRange[0] == merged[-1].mRange[1] + 1:
            merged[-1].mRange = (merged[-1].mRange[0], sp.mRange[1])
        else:
            merged.append(sp)
    return merged


def build_nct_mask(s: stream.Score, harmonies: list[HarmonyEvent]) -> list[NCTEvent]:
    """
    Very coarse chord-tone vs NCT tagging based on nearest harmony event.
    These flags let a generator drop busy, non-essential tones in LH patterns.
    """
    # Build a simple lookup by time
    h_times = [(h.offset, h) for h in harmonies]
    h_times.sort(key=lambda x: x[0])

    def harmony_at(t: float) -> HarmonyEvent | None:
        last = None
        for off, h in h_times:
            if t >= off:
                last = h
            else:
                break
        return last

    events: list[NCTEvent] = []

    for pi, p in enumerate(s.parts):
        part_name = p.partName or f"Part{pi+1}"
        prev_note: note.Note | None = None
        prev_time: float | None = None

        # Iterate over notes and rests; expand chords into their notes
        for el in p.flatten().notesAndRests:
            if isinstance(el, note.Rest):
                continue

            t = elem_offset(el)
            # Collect note(s) at this onset
            if isinstance(el, note.Note):
                onset_notes = [el]
            elif isinstance(el, chord.Chord):
                onset_notes = list(el.notes)
            else:
                continue

            h = harmony_at(t)
            chord_tones = set()
            if h and h.root:
                chord_tones = {h.root.lower()}

            weak = (getattr(el, "beatStrength", 0.0) or 0.0) < 0.5
            time_advanced = prev_time is None or abs(t - prev_time) > 1e-6

            for n_single in onset_notes:
                is_ct = n_single.pitch.name.lower() in chord_tones
                nct_type = None
                keep = is_ct

                # Only classify via interval when moving to a new onset time
                if not is_ct and prev_note is not None and time_advanced:
                    intv = abs(interval.notesToInterval(prev_note, n_single).semitones)
                    if intv in (1, 2) and weak:
                        nct_type = "passing"
                    elif intv in (1, 2) and not weak:
                        nct_type = "suspOrApp"
                    else:
                        nct_type = "other"

                events.append(
                    NCTEvent(
                        offset=t,
                        part=part_name,
                        pitch=pitch_name(n_single),
                        isChordTone=is_ct,
                        nctType=nct_type,
                        keep=keep,
                    )
                )

            # After processing all notes at this onset, update prev references
            prev_note = onset_notes[-1]
            prev_time = t

    return events


def extract_ranges(s: stream.Score) -> Ranges:
    """Compute RH/LH pitch bounds for ergonomic voicing targets in the simplified LH."""
    def part_range(p: stream.Part) -> dict[str, str]:
        # Expand chords to their member pitches and compute min/max by MIDI
        min_midi = None
        max_midi = None
        for el in p.flatten().getElementsByClass([note.Note, chord.Chord]):
            if isinstance(el, note.Note):
                cand_midis = [el.pitch.midi]
            else:
                cand_midis = [n.pitch.midi for n in el.notes]
            for m in cand_midis:
                min_midi = m if min_midi is None or m < min_midi else min_midi
                max_midi = m if max_midi is None or m > max_midi else max_midi
        if min_midi is None or max_midi is None:
            return {"min": "", "max": ""}
        # Convert MIDI back to pitch labels using a temporary Note
        return {
            "min": note.Note(min_midi).nameWithOctave,
            "max": note.Note(max_midi).nameWithOctave,
        }

    if len(s.parts) >= 2:
        RH = part_range(s.parts[0])
        LH = part_range(s.parts[-1])
    elif len(s.parts) == 1:
        # Single part: rough split by pitch median to emulate RH/LH bounds
        p = s.parts[0]
        # Collect all MIDI values, expanding chords
        all_midis: list[int] = []
        for el in p.flatten().getElementsByClass([note.Note, chord.Chord]):
            if isinstance(el, note.Note):
                all_midis.append(el.pitch.midi)
            else:
                all_midis.extend(n.pitch.midi for n in el.notes)
        if all_midis:
            sorted_midis = sorted(all_midis)
            median_midi = sorted_midis[len(sorted_midis) // 2]
            rh_midis = [m for m in all_midis if m >= median_midi]
            lh_midis = [m for m in all_midis if m < median_midi]
            RH = {
                "min": note.Note(min(rh_midis)).nameWithOctave if rh_midis else "",
                "max": note.Note(max(rh_midis)).nameWithOctave if rh_midis else "",
            }
            LH = {
                "min": note.Note(min(lh_midis)).nameWithOctave if lh_midis else "",
                "max": note.Note(max(lh_midis)).nameWithOctave if lh_midis else "",
            }
        else:
            RH = {"min": "", "max": ""}
            LH = {"min": "", "max": ""}
    else:
        RH = {"min": "", "max": ""}
        LH = {"min": "", "max": ""}
    return Ranges(RH=RH, LH=LH)


def detect_cadences(harmonies: list[HarmonyEvent], key_map: list[KeyArea]) -> list[Cadence]:
    """
    Very simple cadence detector: looks for V→I (PAC/IAC bucket) and deceptive V→vi.
    Even a coarse cadence map helps place stronger LH arrivals and pedal releases.
    """
    out: list[Cadence] = []
    last_rn = None
    for h in harmonies:
        rn = h.rn or ""
        if last_rn:
            pair = (last_rn.upper().replace(" ", ""), rn.upper().replace(" ", ""))
            if pair[0].startswith("V") and (pair[1] == "I" or pair[1].startswith("I")):
                out.append(Cadence(mEnd=-1, type="PAC/IAC", key=key_map[-1].localKey if key_map else "Unknown"))
            elif pair[0].startswith("V") and pair[1].startswith("VI"):
                out.append(Cadence(mEnd=-1, type="Deceptive", key=key_map[-1].localKey if key_map else "Unknown"))
        last_rn = rn
    return out

# -------------------------------
# Orchestrator
# -------------------------------

def build_analysis_bundle(path: str, preferences: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Parse the score and assemble the full analysis bundle that a downstream
    "simplify the accompaniment, keep the melody" engine can consume.
    """
    s = converter.parse(path)

    md = extract_metadata(s)
    keys = detect_key_map(s)
    harms = extract_harmonies(s)
    mel = extract_melody(s)
    bass = extract_bassline(s)
    tex = classify_lh_texture(s)
    nct = build_nct_mask(s, harms)
    rng = extract_ranges(s)
    cad = detect_cadences(harms, keys)

    bundle = {
        "metadata": asdict(md),
        "keys": [asdict(k) for k in keys],
        "harmonies": [asdict(h) for h in harms],
        "melody": [asdict(m) for m in mel],
        "bassline": [asdict(b) for b in bass],
        "textureLH": [asdict(t) for t in tex],
        "nctMask": [asdict(e) for e in nct],
        "ranges": asdict(rng),
        "cadences": [asdict(c) for c in cad],
        "preferences": preferences or asdict(Preferences()),
    }
    return to_jsonable(bundle)

def generate_analysis_of_musicxml(musicxml_path: str,
                                  preferences: dict[str, Any] | None = None,
                                  out_dir: str = ".") -> None:
    """
    Programmatic entry point: build and return the analysis bundle for a MusicXML file.
    Mirrors the legacy generate_legacy_analysis_of_musicxml() shape.
    """
    bundle = build_analysis_bundle(musicxml_path, preferences)

    # Write to JSON file in out_dir with _analysis suffix
    basename = Path(musicxml_path).stem
    out_path = Path(out_dir) / f"{basename}_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote analysis to {out_path}")
