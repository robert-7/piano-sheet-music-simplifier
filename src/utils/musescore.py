import logging
import shutil
from pathlib import Path

from music21 import environment

from src.utils import build_utils
from src.utils import score_utils

logger = logging.getLogger(__name__)


def _detect_musescore() -> str | None:
    """
    Detect the MuseScore executable on the system, preferring a Flatpak wrapper if present.

    Returns:
        str | None: The path to the MuseScore executable if found, otherwise None.
    """
    # Prefer your Flatpak wrapper if you created it:
    wrapper = Path("/usr/local/bin/musescore")
    if wrapper.exists():
        logger.info(f"Found musescore at: {wrapper}")
        return str(wrapper)
    # Otherwise, try native binaries
    for name in ("musescore", "mscore", "musescore3"):
        p = shutil.which(name)
        if p:
            logger.info(f"Found musescore at: {p}")
            return p
    logger.warning("Could not find musescore executable.")
    return None

def convert_musicxml_to_pdf(musicxml_path: str, *, overwrite: bool = False) -> Path:
    """
    Render a MusicXML/MXL file to PDF with MuseScore.
    Output file is <stem>.MuseScore.pdf in the same directory.

    Returns: Path to the generated PDF.
    Raises:  FileNotFoundError if input doesn't exist; RuntimeError if MuseScore fails.
    """
    src = Path(musicxml_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)

    mscore = _detect_musescore()
    if not mscore:
        raise RuntimeError("MuseScore executable not found.")

    out_dir, stem = src.parent, src.stem
    us = environment.UserSettings()
    us["musicxmlPath"] = mscore
    us['musescoreDirectPNGPath'] = mscore
    dst = out_dir / f"{stem}.MuseScore.pdf"

    if build_utils.needs_build(src, dst, overwrite=overwrite):
        logger.info(f"Converting {src} to {dst} with MuseScore...")
        score = score_utils.load_score(str(src))
        score.write("musicxml.pdf", fp=str(dst))
    else:
        logger.info(f"Skipping {dst}, already up to date.")

    return dst
