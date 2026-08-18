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

    if len(result.outputs) != 1:
        raise RuntimeError(
            f"Expected Audiveris to produce a single merged MusicXML file for {pdf_path}, "
            f"but got {len(result.outputs)}: {', '.join(str(p) for p in result.outputs)}. "
            "This usually means the PDF was rasterized into per-page images before being "
            "passed to Audiveris, which exports one book per page."
        )

    return result.outputs[0]
