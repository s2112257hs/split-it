# backend/app/domain/split_logic.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


class SplitLogicError(ValueError):
    """Raised when split inputs are invalid."""


@dataclass(frozen=True)
class Allocation:
    """
    Allocation result for a single item split among selected participants.

    amounts_cents is ordered to match the provided participants order.
    """
    total_cents: int
    participants: Tuple[str, ...]
    amounts_cents: Tuple[int, ...]


def split_cents_penny_perfect(total_cents: int, participants: Sequence[str]) -> Allocation:
    """
    Split an integer number of cents across participants using the MVP algorithm:

      base = total_cents // m
      remainder = total_cents % m
      first 'remainder' participants get base + 1, rest get base

    Returns an Allocation whose amounts align to the participants order.
    """
    if not isinstance(total_cents, int):
        raise SplitLogicError("total_cents must be an int")
    if total_cents < 0:
        raise SplitLogicError("total_cents must be >= 0")

    if not isinstance(participants, (list, tuple)):
        raise SplitLogicError("participants must be a sequence")

    if len(participants) == 0:
        raise SplitLogicError("participants must contain at least 1 participant")

    # Ensure stable ordering and no empty ids
    norm: List[str] = []
    for p in participants:
        if not isinstance(p, str):
            raise SplitLogicError("participant ids must be strings")
        if p.strip() == "":
            raise SplitLogicError("participant ids must be non-empty strings")
        norm.append(p)

    m = len(norm)
    base = total_cents // m
    remainder = total_cents % m

    amounts = [base + 1 if i < remainder else base for i in range(m)]
    # Safety: ensure penny-perfect sum
    if sum(amounts) != total_cents:
        raise SplitLogicError("internal error: allocation does not sum to total")

    return Allocation(
        total_cents=total_cents,
        participants=tuple(norm),
        amounts_cents=tuple(amounts),
    )


def add_allocation_to_totals(
    totals_by_participant: Dict[str, int], allocation: Allocation
) -> Dict[str, int]:
    """
    Add an Allocation into a running totals dict (cents).
    Mutates and also returns the dict for convenience.
    """
    for pid, cents in zip(allocation.participants, allocation.amounts_cents, strict=True):
        totals_by_participant[pid] = totals_by_participant.get(pid, 0) + cents
    return totals_by_participant


def split_items_and_sum(
    items: Iterable[Tuple[str, int, Sequence[str]]]
) -> Dict[str, int]:
    """
    Convenience helper for end-to-end usage.

    items: iterable of (item_id, item_total_cents, participants_for_item)

    Returns totals_by_participant in cents.

    Notes:
    - item_id is not used by the math, but is included for interface symmetry.
    - This function enforces penny-perfectness per item.
    """
    totals: Dict[str, int] = {}
    for _item_id, cents, pids in items:
        alloc = split_cents_penny_perfect(cents, pids)
        add_allocation_to_totals(totals, alloc)
    return totals
