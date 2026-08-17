#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import cv2
from pdf2image import convert_from_path

from src.piano_learning.utils import fs_utils


def pdf_to_images(pdf_path: Path, out_dir: Path, dpi: int = 400) -> list[Path]:
    """
    Convert PDF pages to PNG images at `dpi` using pdf2image.
    """
    fs_utils.ensure_dir(out_dir)
    pages = convert_from_path(str(pdf_path), dpi=dpi)
    img_paths: list[Path] = []
    for i, img in enumerate(pages, start=1):
        p = out_dir / f"page-{i:03d}.png"
        img.save(p)
        img_paths.append(p)
    return img_paths


def preprocess_images_inplace(img_paths: list[Path]) -> None:
    """
    Optional cleanup using OpenCV: grayscale + adaptive threshold.
    """
    for p in img_paths:
        im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if im is None:
            continue
        # adaptive threshold helps with uneven backgrounds; tweak if needed
        im = cv2.adaptiveThreshold(
            im, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 15
        )
        cv2.imwrite(str(p), im)
