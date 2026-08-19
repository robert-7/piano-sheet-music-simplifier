#!/usr/bin/env python3
"""Score metadata helpers: recover title/composer and stop placeholder pollution.

Two concerns live here, both about the title/composer/movement metadata that
should survive from the input score to the rendered PDF:

- ``read_pdf_metadata`` / ``backfill_musicxml_metadata`` recover a title and
  composer from a PDF's document properties and write them into a MusicXML file
  *only where they are missing*, so higher-confidence values captured upstream
  (e.g. text OCR'd by Audiveris) always win.
- ``normalize_output_metadata`` strips the placeholders music21 injects on
  export (the source file name as the title, and its ``Music21`` /
  ``Music21 Fragment`` defaults for an unset composer/title).
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Notation tools embed their source project file name in the PDF /Title
# (e.g. "Kakariko Village.musx"); the trailing suffix is stripped so the value
# reads as a piece title rather than a file name.
_NOTATION_SUFFIXES = (
    ".musx",
    ".mscz",
    ".mscx",
    ".mxl",
    ".musicxml",
    ".xml",
    ".mid",
    ".midi",
    ".cap",
    ".capx",
    ".sib",
    ".mus",
    ".pdf",
)

_DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>]*>")


def clean_title(raw: str | None) -> str | None:
    """Normalize a raw PDF title into a display title, or ``None`` if empty."""
    if not raw:
        return None
    text = raw.strip()
    lowered = text.lower()
    for suffix in _NOTATION_SUFFIXES:
        if lowered.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    return text or None


def read_pdf_metadata(pdf_path: str | Path) -> tuple[str | None, str | None]:
    """Return ``(title, composer)`` from a PDF's document-info dictionary.

    Best-effort fallback for scores whose printed title/composer text could not
    be OCR'd. Never raises: any read failure yields ``(None, None)`` so metadata
    backfill can never break the conversion pipeline.
    """
    try:
        from pypdf import PdfReader

        info = PdfReader(str(pdf_path)).metadata
        if info is None:
            return None, None
        title = clean_title(info.title)
        composer = info.author.strip() if info.author else None
        return title, (composer or None)
    except Exception:
        logger.warning("Could not read PDF document metadata from %s", pdf_path, exc_info=True)
        return None, None


def _text(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _has_title(root: ET.Element) -> bool:
    """Whether the score already carries a title in any MusicXML slot.

    Audiveris stores an OCR'd title in ``<movement-title>`` (not
    ``<work><work-title>``), so both are checked: a title recovered upstream must
    suppress the lower-confidence PDF fallback.
    """
    work = root.find("work")
    if work is not None and _text(work.find("work-title")):
        return True
    return bool(_text(root.find("movement-title")))


def _has_composer(root: ET.Element) -> bool:
    identification = root.find("identification")
    if identification is None:
        return False
    return any(
        creator.get("type") == "composer" and bool(_text(creator))
        for creator in identification.findall("creator")
    )


def backfill_musicxml_metadata(
    xml_path: str | Path,
    title: str | None = None,
    composer: str | None = None,
) -> bool:
    """Fill in a missing work-title / composer on a ``score-partwise`` MusicXML file.

    Only *missing* fields are written, so genuine metadata captured upstream
    (e.g. an OCR'd title/composer from Audiveris) always takes precedence over
    the lower-confidence values passed here. Returns whether the file changed.

    Insertions respect MusicXML element order: ``<work>`` is the first child of
    ``<score-partwise>`` and ``<creator>`` is the first child of
    ``<identification>``.
    """
    if not title and not composer:
        return False

    xml_path = Path(xml_path)
    original = xml_path.read_text(encoding="utf-8")
    # ElementTree discards comments and the DOCTYPE on parse; keep both so the
    # rewritten file stays a faithful MusicXML document.
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(original, parser=parser)
    if root.tag != "score-partwise":
        return False

    changed = False

    if title and not _has_title(root):
        work = ET.Element("work")
        ET.SubElement(work, "work-title").text = title
        root.insert(0, work)
        changed = True

    if composer and not _has_composer(root):
        identification = root.find("identification")
        if identification is None:
            identification = ET.Element("identification")
            # <identification> follows work/movement-* but precedes the rest;
            # insert it right after any of those to keep a valid document order.
            insert_at = 0
            for index, child in enumerate(list(root)):
                if child.tag in ("work", "movement-number", "movement-title"):
                    insert_at = index + 1
            root.insert(insert_at, identification)
        creator = ET.Element("creator")
        creator.set("type", "composer")
        creator.text = composer
        identification.insert(0, creator)
        changed = True

    if changed:
        doctype_match = _DOCTYPE_RE.search(original)
        doctype = f"{doctype_match.group(0)}\n" if doctype_match else ""
        body = ET.tostring(root, encoding="unicode")
        xml_path.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n{doctype}{body}\n', encoding="utf-8")

    return changed


def normalize_output_metadata(score: Any, source_name: str | Path | None = None) -> None:
    """Strip music21's placeholder title/composer from a score before export.

    music21 seeds ``movementName`` from the *source file name* on parse (when the
    score has no ``<movement-title>``) and, on export, substitutes
    ``defaults.author`` ("Music21") / ``defaults.title`` ("Music21 Fragment")
    whenever the composer/title are unset -- all of which surface as bogus
    metadata in the rendered PDF.

    Only the file-name placeholder is removed: a real title (an OCR'd
    ``<movement-title>`` or a work title) is left intact. Pass ``source_name`` for
    an exact match; otherwise a music-file suffix is used to spot the placeholder.
    """
    import music21

    music21.defaults.author = ""
    music21.defaults.title = ""
    metadata = getattr(score, "metadata", None)
    if metadata is None:
        return

    movement = (metadata.movementName or "").strip()
    is_placeholder = movement.lower().endswith((".xml", ".musicxml", ".mxl"))
    if source_name is not None:
        name = Path(source_name).name
        is_placeholder = is_placeholder or movement in (name, Path(name).stem)
    if is_placeholder:
        # Replace the file name with the real work title if there is one, else drop it.
        metadata.movementName = metadata.title
