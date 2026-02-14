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
 * Penny-perfect split with fair remainder allocation:
 * For each item assigned to m people:
 * - base = cents // m (given to all selected participants)
 * - rem  = cents % m
 * - each remainder cent goes to the selected participant with the
 *   lowest running total at that moment.
 * Tie-break: earlier participant in participants[] wins.
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

    // Base allocation first.
    selectedValid.forEach((pid) => {
      totals.set(pid, (totals.get(pid) ?? 0) + base);
    });

    // Fair remainder allocation: lowest running total wins, then stable order.
    for (let i = 0; i < rem; i += 1) {
      const selectedPid = selectedValid.reduce((bestPid, candidatePid) => {
        const bestTotal = totals.get(bestPid) ?? 0;
        const candidateTotal = totals.get(candidatePid) ?? 0;

        if (candidateTotal < bestTotal) return candidatePid;
        if (candidateTotal > bestTotal) return bestPid;

        return (participantIndex.get(candidatePid) ?? Number.MAX_SAFE_INTEGER) <
          (participantIndex.get(bestPid) ?? Number.MAX_SAFE_INTEGER)
          ? candidatePid
          : bestPid;
      }, selectedValid[0]);

      totals.set(selectedPid, (totals.get(selectedPid) ?? 0) + 1);
    }
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
