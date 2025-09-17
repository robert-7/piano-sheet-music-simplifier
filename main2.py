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
from datetime import datetime
from pathlib import Path

from src import audiveris

# --------------------------
# CLI
# --------------------------

def main():
    # Generate a timestamped output directory name
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    default_out_dir = Path(f"./user/output-{timestamp}")

    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path", type=Path, help="Path to the input PDF")
    ap.add_argument("--out", type=Path, default=default_out_dir, help="Output directory")
    ap.add_argument("--no-rasterize", action="store_true", help="Let Audiveris read the PDF directly")
    ap.add_argument("--dpi", type=int, default=400, help="DPI for rasterization")
    ap.add_argument("--audiveris", type=str, default=None, help="Path to audiveris executable")
    args = ap.parse_args()

    result = audiveris.convert_pdf_to_musicxml(
        pdf_path=args.pdf_path,
        out_dir=args.out,
        prefer_rasterize=not args.no_rasterize,
        dpi=args.dpi,
        audiveris_path=args.audiveris,
    )

    print(f"\nAudiveris outputs ({len(result.outputs)}):")
    for p in result.outputs:
        print("  ", p)

    print(f"\nLog: {result.log_path}")

if __name__ == "__main__":
    main()
