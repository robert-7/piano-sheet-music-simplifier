import logging
from pathlib import Path
from typing import Dict

from src.utils import lilypond
from src.utils import musescore

logger = logging.getLogger(__name__)


def convert_musicxml_to_pdfs(
    musicxml_path: str, out_dir: Path, convert_with_lilypond: bool, convert_with_musescore: bool, overwrite: bool
) -> Dict[str, Path]:
    """
    Render a MusicXML/MXL file to PDF with both LilyPond and MuseScore (when available).
    Output files are <stem>.LilyPond.pdf and <stem>.MuseScore.pdf in the same directory.

    Returns: dict { 'LilyPond': Path, 'MuseScore': Path } for the backends that succeeded.
    Raises:  FileNotFoundError if input doesn't exist; RuntimeError if no backend could produce a PDF.
    """
    results: Dict[str, Path] = {}
    errors: Dict[str, Exception] = {}

    key = "LilyPond"
    if convert_with_lilypond:
        logger.info("Converting with LilyPond...")
        try:
            results[key] = lilypond.convert_musicxml_to_pdf(musicxml_path, out_dir=out_dir, overwrite=overwrite)
        except (FileNotFoundError, RuntimeError) as e:
            errors[key] = e
            logger.error(f"{key} failed: {e}")

    key = "MuseScore"
    if convert_with_musescore:
        logger.info("Converting with MuseScore...")
        try:
            results[key] = musescore.convert_musicxml_to_pdf(musicxml_path, out_dir=out_dir, overwrite=overwrite)
        except (FileNotFoundError, RuntimeError) as e:
            errors[key] = e
            logger.error(f"{key} failed: {e}")

    if not results:
        msg = ["Could not generate a PDF with LilyPond or MuseScore."]
        for k, e in errors.items():
            msg.append(f"{k} error: {e}")
        raise RuntimeError("\n".join(msg))

    return results


def convert_musicxml_to_pdf(musicxml_path: str, out_dir: Path, convert_with_lilypond: bool, convert_with_musescore: bool, overwrite: bool):
    outputs = convert_musicxml_to_pdfs(musicxml_path, out_dir, convert_with_lilypond=convert_with_lilypond, convert_with_musescore=convert_with_musescore, overwrite=overwrite)
    for backend, path in outputs.items():
        logger.info(f"✅ The PDF can be found in: {backend} → {path}")
