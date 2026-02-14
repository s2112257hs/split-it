# backend/app/services/receipt_parser.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

from app.domain.money import MoneyError, parse_usd_to_cents


class ReceiptParseError(ValueError):
    """Raised when parsing fails or inputs are invalid."""


@dataclass(frozen=True)
class ParsedItem:
    description: str
    price_cents: int


# Price token expected at end of line. We keep it permissive because
# parse_money_to_cents() does the strict validation.
#
# Captures examples:
#   12.34
#   $12.34
#   12.34-
#   $12.34-
#   12,34
#   $12
_PRICE_AT_END_RE = re.compile(
    r"""
    (?P<token>
      \$?\s*                 # optional $
      \d{1,7}                # digits
      (?:[.,]\d{1,2})?       # optional decimals
      \s*-?                  # optional trailing dash
    )
    \s*$                     # end of line
    """,
    re.VERBOSE,
)

# Common receipt summary lines we skip by default (conservative).
_EXCLUDE_KEYWORDS = (
    "subtotal",
    "sub total",
    "tax",
    "vat",
    "tip",
    "gratuity",
    "service",
    "total",
    "balance",
    "change",
    "cash",
    "card",
    "visa",
    "mastercard",
    "amex",
    "amount due",
)


def _looks_like_summary_line(text: str) -> bool:
    t = " ".join(text.lower().split())
    return any(k in t for k in _EXCLUDE_KEYWORDS)


def extract_items_from_lines(
    lines: Sequence[str],
    *,
    exclude_summary_lines: bool = True,
    min_price_cents: int = 1,
) -> List[ParsedItem]:
    """
    Extract items from OCR'd receipt lines.

    Conservative approach:
    - Look for a money-like token at end of the line
    - Parse it with parse_money_to_cents() (single source of truth)
    - Description is everything before the token
    - Optionally skip summary lines like TOTAL/TAX/etc.
    - Skip items with abs(price) < min_price_cents
    """
    if not isinstance(lines, (list, tuple)):
        raise ReceiptParseError("lines must be a sequence of strings")

    items: List[ParsedItem] = []
    for raw in lines:
        if not isinstance(raw, str):
            raise ReceiptParseError("each line must be a string")
        line = raw.strip()
        if not line:
            continue

        if exclude_summary_lines and _looks_like_summary_line(line):
            continue

        m = _PRICE_AT_END_RE.search(line)
        if not m:
            continue

        token = m.group("token").strip()
        try:
            price_cents = parse_usd_to_cents(token, allow_negative=True)
        except MoneyError:
            continue

        if abs(price_cents) < min_price_cents:
            continue

        desc = line[: m.start("token")].strip()
        if not desc:
            continue

        items.append(ParsedItem(description=desc, price_cents=price_cents))

    return items


def extract_items_from_ocr_text(
    ocr_text: str,
    *,
    exclude_summary_lines: bool = True,
    min_price_cents: int = 1,
) -> List[ParsedItem]:
    """
    Convenience: split OCR text by newlines, then run extract_items_from_lines.
    """
    if not isinstance(ocr_text, str):
        raise ReceiptParseError("ocr_text must be a string")

    return extract_items_from_lines(
        ocr_text.splitlines(),
        exclude_summary_lines=exclude_summary_lines,
        min_price_cents=min_price_cents,
    )
