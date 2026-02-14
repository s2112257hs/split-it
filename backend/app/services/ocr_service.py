# backend/app/services/ocr_service.py
from __future__ import annotations

from typing import List

import numpy as np
import cv2
import easyocr


class OcrError(RuntimeError):
    pass


# Lazy-init so the model loads once (fast for repeated API calls)
_READER: easyocr.Reader | None = None


def _get_reader() -> easyocr.Reader:
    global _READER
    if _READER is None:
        # English is enough for most receipts; add languages if needed.
        # gpu=False avoids CUDA issues and works everywhere.
        _READER = easyocr.Reader(["en"], gpu=False)
    return _READER


def run_ocr(image_bytes: bytes) -> str:
    """
    Convert image bytes -> OCR text (newline-separated).
    Designed for receipt_parser.extract_items_from_ocr_text(...).
    """
    if not isinstance(image_bytes, (bytes, bytearray)) or len(image_bytes) == 0:
        raise OcrError("image_bytes must be non-empty bytes")

    # Decode bytes into an image (OpenCV)
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise OcrError("Could not decode image bytes")

    # Light preprocessing for receipts (improves OCR stability)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 11
    )

    reader = _get_reader()

    # detail=0 returns just the text strings; paragraph=True groups words into lines better
    lines: List[str] = reader.readtext(gray, detail=0, paragraph=True)

    # Return newline-separated text for your existing parser
    return "\n".join([ln.strip() for ln in lines if str(ln).strip()])
