# backend/app/domain/money.py
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional


class MoneyError(ValueError):
    """Raised when currency/money parsing or formatting fails."""


@dataclass(frozen=True)
class Money:
    """
    Simple money value object using integer cents (USD by default).
    No floats anywhere.
    """
    cents: int
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not isinstance(self.cents, int):
            raise MoneyError("Money.cents must be an int")
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise MoneyError("Money.currency must be a non-empty string")

    @property
    def dollars(self) -> Decimal:
        return Decimal(self.cents) / Decimal(100)

    def format(self, symbol: str = "$") -> str:
        """
        Format cents as a string like "$12.34".
        """
        sign = "-" if self.cents < 0 else ""
        abs_cents = abs(self.cents)
        dollars = abs_cents // 100
        cents = abs_cents % 100
        return f"{sign}{symbol}{dollars}.{cents:02d}"


# Conservative money-token parsing:
# - Supports $ prefix, optional spaces, decimal "." or ","
# - Supports trailing "-" meaning negative (common on receipts)
# - Rejects thousands separators to avoid guessing ("1,234.56")
_MONEY_TOKEN_RE = re.compile(r"^\s*\$?\s*(\d{1,7})([.,](\d{1,2}))?\s*(-)?\s*$")


def parse_usd_to_cents(
    token: str,
    *,
    allow_negative: bool = True,
    max_abs_cents: int = 10_000_000_00,  # $10,000,000.00 safety bound
) -> int:
    """
    Parse a human/OCR money token into integer cents.

    Accepts examples:
      "12" -> 1200
      "12.34" -> 1234
      "$12.34" -> 1234
      "12,34" -> 1234  (decimal comma)
      "5.00-" -> -500  (trailing dash indicates negative)

    Rejects:
      "1,234.56" (thousands separator ambiguity)
      "12.345"
      "abc"
      "-12.34" (leading '-' not supported; receipts often use trailing '-')
    """
    if not isinstance(token, str):
        raise MoneyError("token must be a string")

    s = token.strip()
    if s == "":
        raise MoneyError("token is empty")

    # Reject thousands separators like 1,234.56 or 1,234
    if re.search(r"\d,\d{3}", s):
        raise MoneyError(f"ambiguous thousands separator format: {token}")

    m = _MONEY_TOKEN_RE.match(s)
    if not m:
        raise MoneyError(f"invalid money token: {token}")

    whole = m.group(1)  # digits
    dec_sep = m.group(2)  # like ".34" or ",34" or None
    dec_digits = m.group(3)  # "34" or "3" or None
    trailing_dash = m.group(4)  # "-" or None

    negative = bool(trailing_dash)
    if negative and not allow_negative:
        raise MoneyError("negative amounts are not allowed")

    # Build cents from whole + decimal digits
    dollars = int(whole)
    cents = 0
    if dec_digits is not None:
        if len(dec_digits) == 1:
            cents = int(dec_digits) * 10
        else:
            cents = int(dec_digits)

    total = dollars * 100 + cents
    if negative:
        total = -total

    if abs(total) > max_abs_cents:
        raise MoneyError("amount exceeds safety limit")

    return total


def cents_to_str(cents: int, *, symbol: str = "$") -> str:
    """
    Convert integer cents to a display string like "$12.34".
    """
    if not isinstance(cents, int):
        raise MoneyError("cents must be an int")
    return Money(cents=cents).format(symbol=symbol)


def decimal_to_cents(
    value: str | Decimal,
    *,
    rounding=ROUND_HALF_UP,
    max_abs_cents: int = 10_000_000_00,
) -> int:
    """
    Convert a decimal-like value to cents with explicit rounding.

    Useful if you ever accept typed amounts like "12.345" and need to round.
    For OCR receipt parsing, prefer parse_money_to_cents (more conservative).

    Examples:
      "12.34" -> 1234
      "12.345" -> 1235 (half-up)
    """
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as e:
        raise MoneyError(f"invalid decimal value: {value}") from e

    cents_decimal = (d * Decimal(100)).quantize(Decimal("1"), rounding=rounding)
    cents = int(cents_decimal)

    if abs(cents) > max_abs_cents:
        raise MoneyError("amount exceeds safety limit")

    return cents


def safe_sum_cents(*values: int) -> int:
    """
    Sum cents with type checks (no floats).
    """
    total = 0
    for v in values:
        if not isinstance(v, int):
            raise MoneyError("all values must be int cents")
        total += v
    return total
