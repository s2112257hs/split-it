import type { AssignmentsMap, Item, Participant } from "../types/split";

export type PersonTotal = {
  participant_id: string;
  participant_name: string;
  total_cents: number;
};

export type PersonItemDetail = {
  item_id: string;
  item_name: string;
  amount_cents: number;
};

export type PersonTotalWithDetails = PersonTotal & {
  items: PersonItemDetail[];
};

export type SplitResult = {
  per_person: PersonTotalWithDetails[];
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
  const details = new Map<string, PersonItemDetail[]>();
  for (const p of participants) totals.set(p.id, 0);
  for (const p of participants) details.set(p.id, []);

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

      if (base > 0) {
        details.get(pid)?.push({
          item_id: item.id,
          item_name: item.description,
          amount_cents: base,
        });
      }
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

      const detailEntries = details.get(selectedPid);
      if (!detailEntries) continue;

      const existingEntry = detailEntries.find((entry) => entry.item_id === item.id);
      if (existingEntry) {
        existingEntry.amount_cents += 1;
      } else {
        detailEntries.push({
          item_id: item.id,
          item_name: item.description,
          amount_cents: 1,
        });
      }
    }
  }

  const per_person: PersonTotalWithDetails[] = participants.map((p) => ({
    participant_id: p.id,
    participant_name: p.name,
    total_cents: totals.get(p.id) ?? 0,
    items: details.get(p.id) ?? [],
  }));

  return {
    per_person,
    receipt_total_cents,
    assigned_total_cents,
    unassigned_item_ids,
  };
}
