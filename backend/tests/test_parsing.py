# backend/tests/test_parsing.py
import pytest

from app.services.receipt_parser import (
    ParsedItem,
    ReceiptParseError,
    extract_items_from_lines,
    extract_items_from_ocr_text,
)
from app.domain.money import parse_usd_to_cents, MoneyError


def test_parse_usd_to_cents_basic_formats():
    assert parse_usd_to_cents("12") == 1200
    assert parse_usd_to_cents("12.34") == 1234
    assert parse_usd_to_cents("$12.34") == 1234
    assert parse_usd_to_cents("12.3") == 1230
    assert parse_usd_to_cents("12,34") == 1234  # decimal comma supported


def test_parse_usd_to_cents_trailing_dash_negative():
    assert parse_usd_to_cents("5.00-") == -500
    assert parse_usd_to_cents("$0.99-") == -99


def test_parse_usd_to_cents_rejects_thousands_separator_to_avoid_guessing():
    with pytest.raises(MoneyError):
        parse_usd_to_cents("1,234.56")
    with pytest.raises(MoneyError):
        parse_usd_to_cents("$1,234")


def test_parse_usd_to_cents_rejects_invalid_tokens():
    for bad in ["", "abc", "$", "12..34", "12.345", "12,3,4", "-12.34"]:
        with pytest.raises(MoneyError):
            parse_usd_to_cents(bad)


def test_extract_items_from_lines_happy_path_end_price():
    lines = [
        "Chicken Burger 12.99",
        "Coke 3.50",
        "Garlic Bread $4.00",
    ]
    items = extract_items_from_lines(lines)
    assert items == [
        ParsedItem(description="Chicken Burger", price_cents=1299),
        ParsedItem(description="Coke", price_cents=350),
        ParsedItem(description="Garlic Bread", price_cents=400),
    ]


def test_extract_items_skips_lines_without_price_at_end():
    lines = [
        "WELCOME TO RESTAURANT",
        "Chicken Burger",
        "Coke ....... 3.50   EXTRA TEXT",  # price not at end -> should be ignored by conservative rule
        "Water 1.00",
    ]
    items = extract_items_from_lines(lines)
    assert items == [ParsedItem(description="Water", price_cents=100)]


def test_extract_items_skips_empty_description():
    # Line starts with price only => no description => skip
    lines = ["12.34"]
    assert extract_items_from_lines(lines) == []


def test_extract_items_summary_lines_excluded_by_default():
    lines = [
        "Chicken Burger 12.99",
        "Subtotal 12.99",
        "Tax 1.04",
        "TOTAL 14.03",
        "Coke 3.50",
    ]
    items = extract_items_from_lines(lines)
    assert items == [
        ParsedItem(description="Chicken Burger", price_cents=1299),
        ParsedItem(description="Coke", price_cents=350),
    ]


def test_extract_items_can_include_summary_lines_if_configured():
    lines = [
        "Subtotal 12.99",
        "TOTAL 14.03",
    ]
    items = extract_items_from_lines(lines, exclude_summary_lines=False)
    assert items == [
        ParsedItem(description="Subtotal", price_cents=1299),
        ParsedItem(description="TOTAL", price_cents=1403),
    ]


def test_extract_items_min_price_filter():
    lines = [
        "Napkin 0.00",
        "Water 0.01",
        "Bread 0.10",
    ]
    items = extract_items_from_lines(lines, min_price_cents=10)
    assert items == [ParsedItem(description="Bread", price_cents=10)]


def test_extract_items_from_ocr_text_splits_newlines():
    ocr_text = "Chicken Burger 12.99\nCoke 3.50\nTOTAL 16.49\n"
    items = extract_items_from_ocr_text(ocr_text)
    assert items == [
        ParsedItem(description="Chicken Burger", price_cents=1299),
        ParsedItem(description="Coke", price_cents=350),
    ]


def test_extract_items_rejects_non_string_lines():
    with pytest.raises(ReceiptParseError):
        extract_items_from_lines(["Coke 3.50", 123])  # type: ignore[list-item]
