import logging
from pathlib import Path

from src.piano_learning.utils import audiveris
from src.piano_learning.utils import metadata_utils

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

    output_path = result.outputs[0]

    # Audiveris only captures title/composer when it can OCR the printed text;
    # for image-only PDFs (and when OCR is unavailable) it emits none. Backfill
    # from the PDF's own document properties, but only where Audiveris left the
    # field blank so any OCR'd value keeps precedence.
    try:
        title, composer = metadata_utils.read_pdf_metadata(pdf_path)
        if metadata_utils.backfill_musicxml_metadata(output_path, title=title, composer=composer):
            logger.info(
                "Backfilled MusicXML metadata from PDF document properties (title=%r, composer=%r).",
                title,
                composer,
            )
    except Exception:
        logger.warning("Failed to backfill MusicXML metadata from PDF; continuing.", exc_info=True)

    return output_path
