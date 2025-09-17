#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src import fs_utils
from src import image_utils


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


@dataclass
class ConversionResult:
    outputs: list[Path]
    log_path: Path | None
    workspace: Path


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
    fs_utils.ensure_dir(out_dir)

    if not audiveris_cmd:
        audiveris_cmd = which_exe(["audiveris", "audiveris.bat"])
    if not audiveris_cmd:
        raise RuntimeError(
            "Audiveris executable not found. Put it on PATH or pass --audiveris /path/to/audiveris"
        )

    args = [audiveris_cmd]
    if batch:
        args.append("-batch")
    if export:
        args.append("-export")
    args += ["-output", str(out_dir)]
    args += [str(p) for p in input_paths]

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

    produced: list[Path] = []
    for ext in (".musicxml", ".xml", ".mxl"):
        produced += list(out_dir.rglob(f"*{ext}"))

    if not produced:
        raise RuntimeError(f"No MusicXML files found in {out_dir}. Check {log_path}.")

    return ConversionResult(outputs=sorted(set(produced)), log_path=log_path, workspace=out_dir)


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
    fs_utils.ensure_dir(out_dir)

    img_dir = out_dir / "images"
    img_paths = []
    if prefer_rasterize:
        img_paths = image_utils.pdf_to_images(pdf_path, img_dir, dpi=dpi)
        if img_paths:
            image_utils.preprocess_images_inplace(img_paths)

    inputs = img_paths if img_paths else [pdf_path]
    return run_audiveris(inputs, out_dir=out_dir, audiveris_cmd=audiveris_path)
