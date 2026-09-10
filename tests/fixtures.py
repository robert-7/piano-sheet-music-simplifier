"""Reusable music21 score builders for regression tests.

See docs/TESTING.md for what each fixture exercises and why it exists.
"""
from music21 import bar
from music21 import chord
from music21 import meter
from music21 import note
from music21 import stream


def two_measure_broken_arpeggio_score() -> stream.Score:
    """A 2-measure, 2-part score with a busy, arpeggiated LH to simplify."""
    score = stream.Score()
    rh = stream.Part()
    lh = stream.Part()

    for number in (1, 2):
        rh_measure = stream.Measure(number=number)
        rh_measure.insert(0, note.Note("C5", quarterLength=4.0))
        rh.append(rh_measure)

        lh_measure = stream.Measure(number=number)
        # A full-measure broken-arpeggio pattern: 4 sixteenth notes per beat,
        # so the beat-window reduction has something to collapse.
        pattern = ["C2", "G2", "C3", "E3"] * 4
        for i, name in enumerate(pattern):
            lh_measure.insert(i * 0.25, note.Note(name, quarterLength=0.25))
        lh.append(lh_measure)

    score.append(rh)
    score.append(lh)
    return score


def alberti_bass_score() -> stream.Score:
    """A 2-measure score whose LH plays a classic Alberti pattern (low-high-mid-high)."""
    score = stream.Score()
    rh = stream.Part()
    lh = stream.Part()

    chords = {1: ("C3", "E3", "G3"), 2: ("D3", "F3", "A3")}
    for number in (1, 2):
        rh_measure = stream.Measure(number=number)
        rh_measure.insert(0, note.Note("C5", quarterLength=4.0))
        rh.append(rh_measure)

        low, mid, high = chords[number]
        lh_measure = stream.Measure(number=number)
        alberti_pattern = [low, high, mid, high]
        for beat, name in enumerate(alberti_pattern):
            lh_measure.insert(float(beat), note.Note(name, quarterLength=1.0))
        lh.append(lh_measure)

    score.append(rh)
    score.append(lh)
    return score


def walking_bass_score() -> stream.Score:
    """A 2-measure score whose LH is already a simple single-note-per-beat line."""
    score = stream.Score()
    rh = stream.Part()
    lh = stream.Part()

    lines = {1: ("C3", "D3", "E3", "F3"), 2: ("G3", "A3", "B3", "C4")}
    for number in (1, 2):
        rh_measure = stream.Measure(number=number)
        rh_measure.insert(0, note.Note("C5", quarterLength=4.0))
        rh.append(rh_measure)

        lh_measure = stream.Measure(number=number)
        for beat, name in enumerate(lines[number]):
            lh_measure.insert(float(beat), note.Note(name, quarterLength=1.0))
        lh.append(lh_measure)

    score.append(rh)
    score.append(lh)
    return score


def pickup_measure_score() -> stream.Score:
    """
    A score with a one-beat pickup (anacrusis) measure 0 in 4/4, followed by one full measure.

    ``paddingLeft`` marks the missing beats at the start of the bar, which is how music21
    (and MusicXML) represent a pickup: the measure's notated duration (1.0 ql) is shorter
    than the notated time signature's bar duration (4.0 ql).
    """
    score = stream.Score()
    rh = stream.Part()
    lh = stream.Part()

    pickup_rh = stream.Measure(number=0)
    pickup_rh.timeSignature = meter.TimeSignature("4/4")
    pickup_rh.paddingLeft = 3.0
    pickup_rh.insert(0, note.Note("C5", quarterLength=1.0))
    rh.append(pickup_rh)

    pickup_lh = stream.Measure(number=0)
    pickup_lh.timeSignature = meter.TimeSignature("4/4")
    pickup_lh.paddingLeft = 3.0
    pickup_lh.insert(0, note.Note("C3", quarterLength=1.0))
    lh.append(pickup_lh)

    full_rh = stream.Measure(number=1)
    full_rh.insert(0, note.Note("D5", quarterLength=4.0))
    rh.append(full_rh)

    full_lh = stream.Measure(number=1)
    full_lh.insert(0, note.Note("D3", quarterLength=4.0))
    lh.append(full_lh)

    score.append(rh)
    score.append(lh)
    return score


def mismatched_voice_ids_score() -> stream.Score:
    """
    A 2-measure score reproducing an Audiveris/OMR pathology that crashes music21 export.

    Measure 1's RH carries an explicit voice ``'2'`` whose content overshoots the barline
    (music21 gives such voices an over-long rest when the source lacks a usable time
    signature -- Audiveris emits exactly this and warns "No target duration ... check time
    signatures"). Measure 2 has voices too, but none with id ``'2'``. On export music21's
    ``makeRests``/``makeTies`` tries ``mNext.voices['2']`` to tie the overshooting rest across
    the barline and raises ``KeyError('2')``. See ``score_utils.dissolve_voices``.
    """
    score = stream.Score()
    rh = stream.Part()
    lh = stream.Part()

    m1_rh = stream.Measure(number=1)
    m1_rh.timeSignature = meter.TimeSignature("4/4")
    v1 = stream.Voice(id="1")
    v1.insert(0, note.Note("C5", quarterLength=4.0))
    v2 = stream.Voice(id="2")
    # Overshoots the 4/4 bar (a breve rest, a single notatable symbol) so makeTies must
    # bridge into the next measure's voice '2'.
    v2.insert(0, note.Rest(quarterLength=8.0))
    m1_rh.insert(0, v1)
    m1_rh.insert(0, v2)
    rh.append(m1_rh)

    m2_rh = stream.Measure(number=2)
    v1b = stream.Voice(id="1")
    v1b.insert(0, note.Note("D5", quarterLength=4.0))
    m2_rh.insert(0, v1b)
    rh.append(m2_rh)

    for number in (1, 2):
        lh_measure = stream.Measure(number=number)
        if number == 1:
            lh_measure.timeSignature = meter.TimeSignature("4/4")
        lh_measure.insert(0, note.Note("C3", quarterLength=4.0))
        lh.append(lh_measure)

    score.append(rh)
    score.append(lh)
    return score


def score_with_repeat_barlines() -> stream.Score:
    """A 2-measure score bracketed by a start repeat on measure 1 and an end repeat on measure 2."""
    score = stream.Score()
    rh = stream.Part()
    lh = stream.Part()

    m1_rh = stream.Measure(number=1)
    m1_rh.timeSignature = meter.TimeSignature("4/4")
    m1_rh.leftBarline = bar.Repeat(direction="start")
    m1_rh.insert(0, note.Note("C5", quarterLength=4.0))
    rh.append(m1_rh)

    m2_rh = stream.Measure(number=2)
    m2_rh.rightBarline = bar.Repeat(direction="end")
    m2_rh.insert(0, note.Note("D5", quarterLength=4.0))
    rh.append(m2_rh)

    m1_lh = stream.Measure(number=1)
    m1_lh.timeSignature = meter.TimeSignature("4/4")
    m1_lh.leftBarline = bar.Repeat(direction="start")
    pattern = ["C2", "G2", "C3", "E3"] * 4
    for i, name in enumerate(pattern):
        m1_lh.insert(i * 0.25, note.Note(name, quarterLength=0.25))
    lh.append(m1_lh)

    m2_lh = stream.Measure(number=2)
    m2_lh.rightBarline = bar.Repeat(direction="end")
    m2_lh.insert(0, chord.Chord(["D2", "A2"], quarterLength=4.0))
    lh.append(m2_lh)

    score.append(rh)
    score.append(lh)
    return score
