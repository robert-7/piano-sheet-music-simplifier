#!/usr/bin/env python3
"""
Convert a sheet-music PDF to MusicXML/MXL using Audiveris, with optional
pre-processing. Then (optionally) parse with music21 for downstream analysis.

Requirements:
- Java 11+ installed
- Audiveris installed (CLI available as `audiveris` or provide path)
Optional:
- pdf2image + Poppler (for PDF -> PNG rasterization)
- opencv-python (cv2) for clean-up (threshold/denoise)

Usage:
    python convert_pdf_to_musicxml.py /path/to/score.pdf --out ./out
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List
from typing import Optional

# --------------------------
# Utilities / environment checks
# --------------------------

def which_exe(candidates: list[str]) -> str | None:
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
    return None

def check_java() -> None:
    try:
        out = subprocess.run(["java", "-version"], capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError("`java -version` failed.")
    except FileNotFoundError as e:
        raise RuntimeError("Java not found. Install Java 11+ and ensure `java` is on PATH.") from e

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

# --------------------------
# Optional PDF -> PNG rasterization
# --------------------------

def pdf_to_images(pdf_path: Path, out_dir: Path, dpi: int = 400) -> list[Path]:
    """
    Convert PDF pages to PNG images at `dpi` using pdf2image if available.
    Falls back to letting Audiveris read the PDF directly if not available.
    """
    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception:
        # No pdf2image: return empty list so caller can call Audiveris directly on the PDF.
        return []

    ensure_dir(out_dir)
    pages = convert_from_path(str(pdf_path), dpi=dpi)
    img_paths: list[Path] = []
    for i, img in enumerate(pages, start=1):
        p = out_dir / f"page-{i:03d}.png"
        img.save(p)
        img_paths.append(p)
    return img_paths

def preprocess_images_inplace(img_paths: list[Path]) -> None:
    """
    Optional cleanup using OpenCV if available: grayscale + adaptive threshold.
    If cv2 is not available, this is a no-op.
    """
    try:
        import cv2  # type: ignore
    except Exception:
        return

    for p in img_paths:
        im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if im is None:
            continue
        # adaptive threshold helps with uneven backgrounds; tweak if needed
        im = cv2.adaptiveThreshold(
            im, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 15
        )
        cv2.imwrite(str(p), im)

# --------------------------
# Audiveris invocation
# --------------------------

@dataclass
class ConversionResult:
    outputs: list[Path]          # .musicxml or .mxl files
    log_path: Path | None     # Audiveris log, if captured
    workspace: Path              # where intermediate files live

def run_audiveris(
    input_paths: list[Path],
    out_dir: Path,
    audiveris_cmd: str | None = None,
    batch: bool = True,
    export: bool = True,
    timeout_sec: int = 1800,
) -> ConversionResult:
    """
    Call Audiveris on either a PDF or a list of images.
    Produces MusicXML (.xml) or compressed MusicXML (.mxl) in `out_dir`.
    """
    ensure_dir(out_dir)

    if not audiveris_cmd:
        audiveris_cmd = which_exe(["audiveris", "audiveris.bat"])
    if not audiveris_cmd:
        raise RuntimeError(
            "Audiveris executable not found. Put it on PATH or pass --audiveris /path/to/audiveris"
        )

    # Audiveris can be run once with multiple inputs. We'll pass them all.
    args = [audiveris_cmd]
    if batch:
        args.append("-batch")
    if export:
        args.append("-export")
    args += ["-output", str(out_dir)]
    args += [str(p) for p in input_paths]

    # Capture logs so you can inspect recognition warnings later.
    log_path = out_dir / "audiveris.log"
    proc = subprocess.run(
        args, capture_output=True, text=True, timeout=timeout_sec
    )
    log_path.write_text(proc.stdout + "\n--- STDERR ---\n" + proc.stderr, encoding="utf-8")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Audiveris failed (code {proc.returncode}). See log: {log_path}\n"
            f"Command: {' '.join(args)}"
        )

    # Collect MusicXML/MXL files Audiveris produced in out_dir (recursively).
    produced: list[Path] = []
    for ext in (".musicxml", ".xml", ".mxl"):
        produced += list(out_dir.rglob(f"*{ext}"))

    if not produced:
        raise RuntimeError(f"No MusicXML files found in {out_dir}. Check {log_path}.")

    return ConversionResult(outputs=sorted(set(produced)), log_path=log_path, workspace=out_dir)

# --------------------------
# High-level conversion API
# --------------------------

def convert_pdf_to_musicxml(
    pdf_path: Path,
    out_dir: Path,
    prefer_rasterize: bool = True,
    dpi: int = 400,
    audiveris_path: str | None = None,
) -> ConversionResult:
    """
    Convert a PDF score to MusicXML/MXL.
    Strategy:
      1) (Optional) rasterize PDF to PNG at high DPI and pre-process images.
      2) Run Audiveris in batch mode with export on either the images or the PDF.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    check_java()
    ensure_dir(out_dir)

    # Option A: rasterize, then OMR
    img_dir = out_dir / "images"
    img_paths = []
    if prefer_rasterize:
        img_paths = pdf_to_images(pdf_path, img_dir, dpi=dpi)
        if img_paths:
            preprocess_images_inplace(img_paths)

    # Pick inputs for Audiveris: images if we have them, otherwise the PDF directly
    inputs = img_paths if img_paths else [pdf_path]
    return run_audiveris(inputs, out_dir=out_dir, audiveris_cmd=audiveris_path)

# --------------------------
# Optional: immediately analyze with your function
# --------------------------

def analyze_with_music21(musicxml_file: Path) -> None:
    """
    Example of feeding the result straight into your analysis.
    """
    from music21 import converter
    from pathlib import Path as _P

    # Import your analyze_harmony if it lives elsewhere; in this snippet we inline a minimal version
    from music21 import roman

    def analyze_harmony(score):
        ks = score.analyze("key")
        chordified = score.chordify()
        chords = chordified.recurse().getElementsByClass("Chord")
        roman_figures = []
        for c in chords:
            pcs = set(c.pitchClasses)
            if len(pcs) < 2:
                continue
            rn = roman.romanNumeralFromChord(c, ks)
            roman_figures.append(rn.figure)
        # Collapse consecutive duplicates for readability
        roman_figures = [x for i, x in enumerate(roman_figures) if i == 0 or x != roman_figures[i-1]]
        print("Estimated key:", ks)
        print("First few Roman numerals:", roman_figures[:40])

    s = converter.parse(str(musicxml_file))
    analyze_harmony(s)

# --------------------------
# CLI
# --------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path, help="Path to the input PDF")
    ap.add_argument("--out", type=Path, default=Path("./audiveris_out"), help="Output directory")
    ap.add_argument("--no-rasterize", action="store_true", help="Let Audiveris read the PDF directly")
    ap.add_argument("--dpi", type=int, default=400, help="DPI for rasterization")
    ap.add_argument("--audiveris", type=str, default=None, help="Path to audiveris executable")
    ap.add_argument("--analyze", action="store_true", help="Immediately parse result with music21 and print a summary")
    args = ap.parse_args()

    result = convert_pdf_to_musicxml(
        pdf_path=args.pdf,
        out_dir=args.out,
        prefer_rasterize=not args.no_rasterize,
        dpi=args.dpi,
        audiveris_path=args.audiveris,
    )

    print(f"\nAudiveris outputs ({len(result.outputs)}):")
    for p in result.outputs:
        print("  ", p)

    print(f"\nLog: {result.log_path}")

    if args.analyze:
        # Pick the largest output (often the full score if multiple files exist)
        best = max(result.outputs, key=lambda p: p.stat().st_size)
        print(f"\nAnalyzing {best} ...\n")
        analyze_with_music21(best)

if __name__ == "__main__":
    main()
