import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def needs_build(src: Path, dst: Path, *, overwrite: bool) -> bool:
    """
    Determine if a destination file needs to be rebuilt based on its existence,
    modification time, or an explicit overwrite flag.

    Args:
        src (Path): The source file path.
        dst (Path): The destination file path.
        overwrite (bool): Whether to force rebuilding the destination file.

    Returns:
        bool: True if the destination file needs to be rebuilt, False otherwise.
    """
    if overwrite:
        logger.info(f"Build forced for {dst} by overwrite flag.")
        return True
    if not dst.exists():
        logger.info(f"Build needed for {dst} because it does not exist.")
        return True
    if dst.stat().st_mtime < src.stat().st_mtime:
        logger.info(f"Build needed for {dst} because it is older than {src}.")
        return True

    logger.info(f"Skipping build for {dst}: already up-to-date and overwrite is false.")
    return False
