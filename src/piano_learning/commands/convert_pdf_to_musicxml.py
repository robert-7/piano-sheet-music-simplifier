import logging
from pathlib import Path

from src.piano_learning.utils import audiveris

logger = logging.getLogger(__name__)


def convert_pdf_to_musicxml(
    pdf_path: Path,
    out_dir: Path,
    prefer_rasterize: bool,
    dpi: int,
):
    """Convert a PDF file to MusicXML using Audiveris."""
    result = audiveris.convert_pdf_to_musicxml(
        pdf_path=pdf_path,
        out_dir=out_dir,
        prefer_rasterize=prefer_rasterize,
        dpi=dpi,
    )

    logger.info(f"Audiveris outputs ({len(result.outputs)}):")
    for p in result.outputs:
        logger.info(f"  {p}")
    logger.info(f"Log: {result.log_path}")

    return result.outputs[0]
