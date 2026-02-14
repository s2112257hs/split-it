# backend/tests/test_split_logic.py
import pytest

from app.domain.split_logic import (
    Allocation,
    SplitLogicError,
    add_allocation_to_totals,
    split_cents_fair_remainder,
    split_cents_penny_perfect,
    split_items_and_sum,
)


def test_equal_split_no_remainder():
    alloc = split_cents_penny_perfect(100, ["a", "b", "c", "d"])
    assert alloc.amounts_cents == (25, 25, 25, 25)
    assert sum(alloc.amounts_cents) == 100


def test_remainder_goes_to_first_r_people():
    # 101 cents split across 4 => base 25, remainder 1
    alloc = split_cents_penny_perfect(101, ["a", "b", "c", "d"])
    assert alloc.amounts_cents == (26, 25, 25, 25)
    assert sum(alloc.amounts_cents) == 101

    # 103 cents split across 4 => base 25, remainder 3
    alloc2 = split_cents_penny_perfect(103, ["a", "b", "c", "d"])
    assert alloc2.amounts_cents == (26, 26, 26, 25)
    assert sum(alloc2.amounts_cents) == 103


def test_participant_order_matters_for_remainder_distribution():
    alloc1 = split_cents_penny_perfect(103, ["a", "b", "c", "d"])
    alloc2 = split_cents_penny_perfect(103, ["d", "c", "b", "a"])
    assert alloc1.amounts_cents == (26, 26, 26, 25)
    assert alloc2.amounts_cents == (26, 26, 26, 25)  # same pattern, different recipients
    # Verify who gets the extra penny depends on order:
    assert dict(zip(alloc1.participants, alloc1.amounts_cents))["a"] == 26
    assert dict(zip(alloc2.participants, alloc2.amounts_cents))["d"] == 26


def test_zero_total_is_all_zeros():
    alloc = split_cents_penny_perfect(0, ["a", "b", "c"])
    assert alloc.amounts_cents == (0, 0, 0)
    assert sum(alloc.amounts_cents) == 0


def test_single_participant_gets_all():
    alloc = split_cents_penny_perfect(999, ["solo"])
    assert alloc.amounts_cents == (999,)
    assert sum(alloc.amounts_cents) == 999


def test_fair_remainder_allocates_to_lowest_running_total():
    running_totals = {"a": 100, "b": 10, "c": 10}
    participant_order = {"a": 0, "b": 1, "c": 2}

    alloc = split_cents_fair_remainder(5, ["a", "b", "c"], running_totals, participant_order)

    # base=1 each => a=101,b=11,c=11 then remainder 2 should go to b then c
    assert alloc.amounts_cents == (1, 2, 2)


def test_fair_remainder_uses_participant_order_for_ties():
    running_totals = {"a": 0, "b": 0}
    participant_order = {"a": 0, "b": 1}

    alloc = split_cents_fair_remainder(1, ["a", "b"], running_totals, participant_order)
    assert alloc.amounts_cents == (1, 0)


def test_invalid_total_type_raises():
    with pytest.raises(SplitLogicError):
        split_cents_penny_perfect("100", ["a", "b"])  # type: ignore[arg-type]


def test_negative_total_raises():
    with pytest.raises(SplitLogicError):
        split_cents_penny_perfect(-1, ["a"])


def test_empty_participants_raises():
    with pytest.raises(SplitLogicError):
        split_cents_penny_perfect(100, [])


def test_non_string_participant_id_raises():
    with pytest.raises(SplitLogicError):
        split_cents_penny_perfect(100, ["a", 123])  # type: ignore[list-item]


def test_blank_participant_id_raises():
    with pytest.raises(SplitLogicError):
        split_cents_penny_perfect(100, ["a", "  "])


def test_add_allocation_to_totals_accumulates():
    totals = {}
    alloc = split_cents_penny_perfect(101, ["a", "b", "c", "d"])  # 26,25,25,25
    add_allocation_to_totals(totals, alloc)
    assert totals == {"a": 26, "b": 25, "c": 25, "d": 25}

    alloc2 = split_cents_penny_perfect(3, ["b", "d"])  # base 1 remainder 1 => b:2 d:1
    add_allocation_to_totals(totals, alloc2)
    assert totals == {"a": 26, "b": 27, "c": 25, "d": 26}


def test_split_items_and_sum_end_to_end_fair_remainder():
    # Receipt order matters:
    # item1: 101 split among a,b -> a=51,b=50
    # item2:  99 split among b,c,d -> base=33 each, no remainder
    totals = split_items_and_sum(
        [
            ("i1", 101, ["a", "b"]),
            ("i2", 99, ["b", "c", "d"]),
        ]
    )
    assert totals == {"a": 51, "b": 83, "c": 33, "d": 33}
    # Ensure grand total matches sum of participant totals
    assert sum(totals.values()) == 200


def test_large_numbers_still_integer_safe():
    alloc = split_cents_penny_perfect(10_000_001, ["a", "b", "c"])
    assert sum(alloc.amounts_cents) == 10_000_001
    # remainder = 2, so first two get +1
    assert alloc.amounts_cents[0] == alloc.amounts_cents[2] + 1
    assert alloc.amounts_cents[1] == alloc.amounts_cents[2] + 1
