import type { AssignmentsMap, Item, Participant } from "../types/split";

export type PersonTotal = {
  participant_id: string;
  participant_name: string;
  total_cents: number;
};

export type SplitResult = {
  per_person: PersonTotal[];
  receipt_total_cents: number;
  assigned_total_cents: number;
  unassigned_item_ids: string[];
};

/**
 * Penny-perfect split:
 * For each item assigned to m people:
 * - base = cents // m
 * - rem  = cents % m
 * First `rem` people (stable order) get base+1, rest get base.
 *
 * Stable order = participant list order (so distribution is deterministic).
 */
export function computePennyPerfectSplit(args: {
  items: Item[];
  participants: Participant[];
  assignments: AssignmentsMap;
}): SplitResult {
  const { items, participants, assignments } = args;

  const receipt_total_cents = items.reduce((s, it) => s + it.price_cents, 0);

  // Init totals map
  const totals = new Map<string, number>();
  for (const p of participants) totals.set(p.id, 0);

  // Deterministic ordering for remainder distribution:
  const participantIndex = new Map<string, number>();
  participants.forEach((p, i) => participantIndex.set(p.id, i));

  const unassigned_item_ids: string[] = [];
  let assigned_total_cents = 0;

  for (const item of items) {
    const selected = assignments[item.id] ?? [];
    const selectedValid = selected
      .filter((pid) => participantIndex.has(pid))
      .sort((a, b) => (participantIndex.get(a)! - participantIndex.get(b)!));

    const m = selectedValid.length;
    if (m === 0) {
      unassigned_item_ids.push(item.id);
      continue;
    }

    const cents = item.price_cents;
    assigned_total_cents += cents;

    const base = Math.trunc(cents / m);
    const rem = cents - base * m; // avoids % edge cases

    selectedValid.forEach((pid, idx) => {
      const add = base + (idx < rem ? 1 : 0);
      totals.set(pid, (totals.get(pid) ?? 0) + add);
    });
  }

  const per_person: PersonTotal[] = participants.map((p) => ({
    participant_id: p.id,
    participant_name: p.name,
    total_cents: totals.get(p.id) ?? 0,
  }));

  return {
    per_person,
    receipt_total_cents,
    assigned_total_cents,
    unassigned_item_ids,
  };
}
