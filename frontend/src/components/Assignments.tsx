import { useEffect, useMemo, useState } from "react";
import type { AssignmentsMap, Item, Participant } from "../types/split";
import { centsToUsdString } from "../lib/money";

type Props = {
  currency: string;
  items: Item[];
  participants: Participant[];
  assignments: AssignmentsMap;
  onChange: (next: AssignmentsMap) => void;
  onBack?: () => void;
  onNext?: () => void;
};

function unique(arr: string[]) {
  return Array.from(new Set(arr));
}

export default function Assignments({
  currency,
  items,
  participants,
  assignments,
  onChange,
  onBack,
  onNext,
}: Props) {
  const [showErrors, setShowErrors] = useState(false);

  const participantIds = useMemo(() => new Set(participants.map((p) => p.id)), [participants]);

  /**
   * Normalize without auto-selecting anyone:
   * - Ensure every item has an entry (default: [])
   * - Remove entries for deleted items
   * - Remove participant IDs that no longer exist
   */
  const normalizedAssignments = useMemo(() => {
    const next: AssignmentsMap = {};

    for (const it of items) {
      const raw = assignments[it.id] ?? [];
      const filtered = raw.filter((pid) => participantIds.has(pid));
      next[it.id] = unique(filtered);
    }

    return next;
  }, [assignments, items, participantIds]);

  /**
   * Seed missing keys once when entering / when items list changes,
   * but DO NOT auto-select participants.
   */
  useEffect(() => {
    // If assignments already has all item keys (or items empty), do nothing.
    const missing = items.some((it) => assignments[it.id] == null);
    const hasExtra = Object.keys(assignments).some((id) => !items.some((it) => it.id === id));
    const hasInvalid = Object.values(assignments).some((arr) => arr?.some((pid) => !participantIds.has(pid)));

    if (!missing && !hasExtra && !hasInvalid) return;

    // Commit normalized map up to parent
    onChange(normalizedAssignments);
    // Hide errors after structural changes; user will re-validate on Next
    setShowErrors(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, participants]); // intentionally not depending on assignments to avoid loops

  const errors = useMemo(() => {
    const e: Record<string, string> = {};
    for (const it of items) {
      const selected = normalizedAssignments[it.id] ?? [];
      if (selected.length === 0) e[it.id] = "Select at least 1 person for this item.";
    }
    return e;
  }, [items, normalizedAssignments]);

  const canNext =
    items.length > 0 &&
    participants.length > 0 &&
    Object.keys(errors).length === 0;

  function setItemSelection(itemId: string, nextSelected: string[]) {
    onChange({
      ...normalizedAssignments,
      [itemId]: unique(nextSelected.filter((pid) => participantIds.has(pid))),
    });
  }

  function toggle(itemId: string, participantId: string) {
    const current = normalizedAssignments[itemId] ?? [];
    const exists = current.includes(participantId);
    const next = exists ? current.filter((x) => x !== participantId) : [...current, participantId];
    setItemSelection(itemId, next);
  }

  function setAllForItem(itemId: string) {
    setItemSelection(itemId, participants.map((p) => p.id));
  }

  function setNoneForItem(itemId: string) {
    // This now truly clears all selections.
    setItemSelection(itemId, []);
  }

  function setAllForAllItems() {
    const allIds = participants.map((p) => p.id);
    const next: AssignmentsMap = {};
    for (const it of items) next[it.id] = allIds;
    onChange(next);
  }

  function setNoneForAllItems() {
    const next: AssignmentsMap = {};
    for (const it of items) next[it.id] = [];
    onChange(next);
  }

  return (
    <div className="stack">
      <div>
        <h2 style={{ margin: 0 }}>Step 4 — Assign items</h2>
        <div className="small" style={{ marginTop: 4 }}>
          Start from none selected, then choose who shares each item.
        </div>
      </div>

      <div className="row" style={{ justifyContent: "flex-end", gap: 10, flexWrap: "wrap" }}>
        <button
          className="btn"
          onClick={setAllForAllItems}
          disabled={participants.length === 0 || items.length === 0}
        >
          Select everyone for all items
        </button>
        <button
          className="btn"
          onClick={setNoneForAllItems}
          disabled={participants.length === 0 || items.length === 0}
        >
          Clear all selections
        </button>
      </div>

      <div className="card stack" style={{ padding: 0 }}>
        <div style={{ padding: 12, borderBottom: "1px solid var(--border)" }}>
          <div className="small">
            {items.length} item(s) • {participants.length} participant(s)
          </div>
        </div>

        <div style={{ display: "grid" }}>
          {items.map((it) => {
            const selected = normalizedAssignments[it.id] ?? [];
            const err = errors[it.id];
            const showErr = showErrors && !!err;

            return (
              <div
                key={it.id}
                style={{
                  padding: 12,
                  borderTop: "1px solid var(--border)",
                }}
              >
                <div className="row" style={{ gap: 12, alignItems: "flex-start" }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700 }}>{it.description || "(No description)"}</div>
                    <div className="small" style={{ marginTop: 2 }}>
                      {centsToUsdString(it.price_cents)} {currency}
                    </div>

                    {showErr && (
                      <div style={{ marginTop: 8, color: "#ffb4c0", fontSize: 12 }}>
                        {err}
                      </div>
                    )}
                  </div>

                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn" onClick={() => setAllForItem(it.id)} disabled={participants.length === 0}>
                      All
                    </button>
                    <button className="btn" onClick={() => setNoneForItem(it.id)} disabled={participants.length === 0}>
                      None
                    </button>
                  </div>
                </div>

                <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 10 }}>
                  {participants.map((p) => {
                    const checked = selected.includes(p.id);
                    return (
                      <label
                        key={p.id}
                        style={{
                          display: "inline-flex",
                          gap: 8,
                          alignItems: "center",
                          padding: "8px 10px",
                          borderRadius: 12,
                          border: "1px solid var(--border)",
                          background: checked ? "rgba(124, 92, 255, 0.14)" : "rgba(255,255,255,0.03)",
                          cursor: "pointer",
                          userSelect: "none",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggle(it.id, p.id)}
                        />
                        <span>{p.name}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="row">
        {onBack && (
          <button className="btn" onClick={onBack}>
            Back
          </button>
        )}

        {onNext && (
          <button
            className="btn btnPrimary"
            onClick={() => {
              if (!canNext) {
                setShowErrors(true);
                return;
              }
              // Ensure parent has the normalized map
              onChange(normalizedAssignments);
              onNext();
            }}
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}
