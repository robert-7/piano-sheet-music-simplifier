import logging
import shutil
from pathlib import Path

from music21 import environment

from src.utils import build_utils
from src.utils import score_utils

logger = logging.getLogger(__name__)


def _detect_lilypond() -> str | None:
    """
    Detect the LilyPond executable on the system.

    Returns:
        str | None: The path to the LilyPond executable if found, otherwise None.
    """
    p = shutil.which("lilypond")
    if p:
        logger.info(f"Found lilypond at: {p}")
        return p
    # common fallback on Ubuntu
    if Path("/usr/bin/lilypond").exists():
        logger.info("Found lilypond at: /usr/bin/lilypond")
        return "/usr/bin/lilypond"
    logger.warning("Could not find lilypond executable.")
    return None

def convert_musicxml_to_pdf(musicxml_path: str, out_dir: Path, overwrite: bool = False) -> Path:
    """
    Render a MusicXML/MXL file to PDF with LilyPond.
    Output file is <stem>.LilyPond.pdf in the same directory.

    Returns: Path to the generated PDF.
    Raises:  FileNotFoundError if input doesn't exist; RuntimeError if LilyPond fails.
    """
    src = Path(musicxml_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)

    lily = _detect_lilypond()
    if not lily:
        raise RuntimeError("LilyPond executable not found.")

    stem = src.stem
    us = environment.UserSettings()
    us["lilypondPath"] = lily
    dst = out_dir / f"{stem}.LilyPond.pdf"

    if build_utils.needs_build(src, dst, overwrite=overwrite):
        logger.info(f"Converting {src} to {dst} with LilyPond...")
        score = score_utils.load_score(str(src))
        score.write("lily.pdf", fp=str(dst))
    else:
        logger.info(f"Skipping {dst}, already up to date.")

    return dst
