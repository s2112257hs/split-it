from __future__ import annotations

from typing import List
from uuid import UUID

from app.db.repository import ParsedItem


class ApiValidationError(ValueError):
    """Raised when request payload validation fails."""


def is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (ValueError, TypeError):
        return False
    return True


def parse_receipt_items(raw_items: object) -> list[ParsedItem]:
    if not isinstance(raw_items, list):
        raise ApiValidationError("'items' must be a list.")

    parsed_items: list[ParsedItem] = []
    for idx, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise ApiValidationError(f"Item at index {idx} must be an object.")

        description = raw_item.get("description")
        price_cents = raw_item.get("price_cents")

        if not isinstance(description, str) or not description.strip():
            raise ApiValidationError(
                f"Item at index {idx} must include a non-empty 'description'."
            )
        if not isinstance(price_cents, int) or price_cents < 0:
            raise ApiValidationError(
                f"Item at index {idx} must include 'price_cents' as int >= 0."
            )

        parsed_items.append(
            ParsedItem(description=description.strip(), price_cents=price_cents)
        )

    return parsed_items


def parse_unique_participant_ids(raw_participants: object) -> List[str]:
    if not isinstance(raw_participants, list) or not raw_participants:
        raise ApiValidationError(
            "'participants' must be a non-empty list of participant ids."
        )

    participant_ids: List[str] = []
    seen_participant_ids: set[str] = set()
    for pid in raw_participants:
        if not isinstance(pid, str) or not is_uuid(pid):
            raise ApiValidationError("Each participant id must be a valid UUID string.")
        if pid in seen_participant_ids:
            raise ApiValidationError("Participant ids must be unique.")
        seen_participant_ids.add(pid)
        participant_ids.append(pid)

    return participant_ids
