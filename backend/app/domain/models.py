# backend/app/domain/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class ModelValidationError(ValueError):
    """Raised when request/response models fail basic validation."""


@dataclass(frozen=True)
class Participant:
    """
    A person taking part in the split.
    No persistence; IDs are provided by client or generated client-side.
    """
    id: str
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ModelValidationError("Participant.id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ModelValidationError("Participant.name must be a non-empty string")


@dataclass(frozen=True)
class Item:
    """
    A receipt line item.
    price_cents is integer cents (USD).
    """
    id: str
    description: str
    price_cents: int

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ModelValidationError("Item.id must be a non-empty string")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ModelValidationError("Item.description must be a non-empty string")
        if not isinstance(self.price_cents, int) or self.price_cents < 0:
            raise ModelValidationError("Item.price_cents must be an int >= 0")


@dataclass(frozen=True)
class SplitRequest:
    """
    Payload for /api/calculate.

    assignments maps item_id -> list of participant_ids who share that item.
    """
    participants: List[Participant]
    items: List[Item]
    assignments: Dict[str, List[str]]

    def __post_init__(self) -> None:
        if not isinstance(self.participants, list) or not self.participants:
            raise ModelValidationError("participants must be a non-empty list")
        if not isinstance(self.items, list):
            raise ModelValidationError("items must be a list")
        if not isinstance(self.assignments, dict):
            raise ModelValidationError("assignments must be a dict")

        pids = [p.id for p in self.participants]
        if len(set(pids)) != len(pids):
            raise ModelValidationError("participant ids must be unique")

        iids = [i.id for i in self.items]
        if len(set(iids)) != len(iids):
            raise ModelValidationError("item ids must be unique")

        pid_set = set(pids)
        iid_set = set(iids)

        # Validate assignments reference known IDs and have non-empty lists
        for item_id, assigned_pids in self.assignments.items():
            if item_id not in iid_set:
                raise ModelValidationError(f"assignment references unknown item id: {item_id}")
            if not isinstance(assigned_pids, list) or not assigned_pids:
                raise ModelValidationError(f"assignment for item {item_id} must be a non-empty list")
            for pid in assigned_pids:
                if pid not in pid_set:
                    raise ModelValidationError(f"assignment references unknown participant id: {pid}")


@dataclass(frozen=True)
class SplitResult:
    """
    Output for /api/calculate.

    totals_by_participant_id values are integer cents (USD).
    grand_total_cents is sum(items[i].price_cents for items included in assignments).
    """
    totals_by_participant_id: Dict[str, int]
    grand_total_cents: int
    currency: str = "USD"
    breakdown_by_item_id: Optional[Dict[str, Dict[str, int]]] = None
    # breakdown_by_item_id (optional):
    #   { item_id: { participant_id: allocated_cents, ... }, ... }

    def __post_init__(self) -> None:
        if not isinstance(self.totals_by_participant_id, dict):
            raise ModelValidationError("totals_by_participant_id must be a dict")
        if not isinstance(self.grand_total_cents, int) or self.grand_total_cents < 0:
            raise ModelValidationError("grand_total_cents must be an int >= 0")
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ModelValidationError("currency must be a non-empty string")

        for pid, cents in self.totals_by_participant_id.items():
            if not isinstance(pid, str) or not pid.strip():
                raise ModelValidationError("totals_by_participant_id keys must be non-empty strings")
            if not isinstance(cents, int) or cents < 0:
                raise ModelValidationError("totals_by_participant_id values must be int >= 0")

        if self.breakdown_by_item_id is not None:
            if not isinstance(self.breakdown_by_item_id, dict):
                raise ModelValidationError("breakdown_by_item_id must be a dict if provided")
            for item_id, per_person in self.breakdown_by_item_id.items():
                if not isinstance(item_id, str) or not item_id.strip():
                    raise ModelValidationError("breakdown item_id keys must be non-empty strings")
                if not isinstance(per_person, dict):
                    raise ModelValidationError("breakdown values must be dicts")
                for pid, cents in per_person.items():
                    if not isinstance(pid, str) or not pid.strip():
                        raise ModelValidationError("breakdown participant_id keys must be non-empty strings")
                    if not isinstance(cents, int) or cents < 0:
                        raise ModelValidationError("breakdown cents must be int >= 0")
