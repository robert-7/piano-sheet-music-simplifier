import shutil
from pathlib import Path

from music21 import converter
from music21 import environment

def _detect_musescore() -> str | None:
    """
    Detect the MuseScore executable on the system, preferring a Flatpak wrapper if present.

    Returns:
        str | None: The path to the MuseScore executable if found, otherwise None.
    """
    # Prefer your Flatpak wrapper if you created it:
    wrapper = Path("/usr/local/bin/musescore")
    if wrapper.exists():
        return str(wrapper)
    # Otherwise, try native binaries
    for name in ("musescore", "mscore", "musescore3"):
        p = shutil.which(name)
        if p:
            return p
    return None

def _needs_build(src: Path, dst: Path, overwrite: bool) -> bool:
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
    return overwrite or (not dst.exists()) or (dst.stat().st_mtime < src.stat().st_mtime)

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

    if _needs_build(src, dst, overwrite):
        score = converter.parse(str(src))
        score.write("musicxml.pdf", fp=str(dst))

    return dst
