from __future__ import annotations

import io
from dataclasses import dataclass
from typing import List, Tuple

import easyocr
import numpy as np
from PIL import Image, ImageOps


class OcrError(RuntimeError):
    pass


_READER: easyocr.Reader | None = None


def _get_reader() -> easyocr.Reader:
    global _READER
    if _READER is None:
        _READER = easyocr.Reader(["en"], gpu=False)
    return _READER


@dataclass(frozen=True)
class _Box:
    x1: float
    y1: float
    x2: float
    y2: float
    text: str
    conf: float

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def h(self) -> float:
        return max(1.0, self.y2 - self.y1)


def _to_boxes(results) -> List[_Box]:
    boxes: List[_Box] = []
    for (bbox, text, conf) in results:
        # bbox = [[x,y],[x,y],[x,y],[x,y]]
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        t = str(text).strip()
        if not t:
            continue
        boxes.append(_Box(min(xs), min(ys), max(xs), max(ys), t, float(conf)))
    return boxes


def _group_into_lines(boxes: List[_Box]) -> List[str]:
    """
    Group OCR boxes into lines by Y-center proximity.
    This is a simple heuristic that works well for receipts.
    """
    if not boxes:
        return []

    # Filter very low confidence noise
    boxes = [b for b in boxes if b.conf >= 0.2]

    # Sort top-to-bottom
    boxes.sort(key=lambda b: (b.cy, b.x1))

    lines: List[List[_Box]] = []
    current: List[_Box] = [boxes[0]]
    current_y = boxes[0].cy
    current_h = boxes[0].h

    for b in boxes[1:]:
        # Dynamic threshold based on typical text height
        thresh = max(10.0, 0.6 * max(current_h, b.h))
        if abs(b.cy - current_y) <= thresh:
            current.append(b)
            # Update running line center/height
            current_y = sum(x.cy for x in current) / len(current)
            current_h = max(current_h, b.h)
        else:
            lines.append(current)
            current = [b]
            current_y = b.cy
            current_h = b.h

    lines.append(current)

    # Within each line, sort left-to-right then join with spaces
    out: List[str] = []
    for line_boxes in lines:
        line_boxes.sort(key=lambda b: b.x1)
        text = " ".join(b.text for b in line_boxes)
        text = " ".join(text.split())
        if text:
            out.append(text)

    return out


def run_ocr(image_bytes: bytes) -> str:
    if not isinstance(image_bytes, (bytes, bytearray)) or len(image_bytes) == 0:
        raise OcrError("image_bytes must be non-empty bytes")

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except Exception as e:
        raise OcrError("Could not decode image bytes") from e

    # Convert to grayscale (helps receipts)
    gray = ImageOps.grayscale(img)
    np_img = np.array(gray)

    reader = _get_reader()

    # detail=1 gives boxes; paragraph=False keeps boxes granular (better for our grouping)
    results = reader.readtext(np_img, detail=1, paragraph=False)

    boxes = _to_boxes(results)
    lines = _group_into_lines(boxes)

    return "\n".join(lines)
