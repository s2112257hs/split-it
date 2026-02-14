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


def split_cents_fair_remainder(
    total_cents: int,
    participants: Sequence[str],
    running_totals: Dict[str, int],
    participant_order: Dict[str, int],
) -> Allocation:
    """
    Split cents with fair remainder allocation using current running totals.

    Steps:
    - Give every selected participant the base amount.
    - Distribute each remainder cent to the selected participant with the
      lowest running total at that moment.
    - Ties are resolved by participant list order via participant_order.
    """
    alloc = split_cents_penny_perfect(total_cents, participants)
    participant_ids = list(alloc.participants)
    participant_idx = {pid: idx for idx, pid in enumerate(participant_ids)}
    m = len(participant_ids)

    base = total_cents // m
    remainder = total_cents % m

    amounts = [base for _ in participant_ids]
    simulated_totals = {
        pid: running_totals.get(pid, 0) + base
        for pid in participant_ids
    }

    for _ in range(remainder):
        selected_pid = min(
            participant_ids,
            key=lambda pid: (simulated_totals[pid], participant_order[pid]),
        )
        amounts[participant_idx[selected_pid]] += 1
        simulated_totals[selected_pid] += 1

    return Allocation(
        total_cents=total_cents,
        participants=tuple(participant_ids),
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
    participant_order: Dict[str, int] = {}

    for _item_id, cents, pids in items:
        for pid in pids:
            if pid not in participant_order:
                participant_order[pid] = len(participant_order)

        alloc = split_cents_fair_remainder(cents, pids, totals, participant_order)
        add_allocation_to_totals(totals, alloc)
    return totals
