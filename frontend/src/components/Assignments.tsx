import { useMemo, useRef, useState } from "react";
import type { AssignmentsMap, Item, Participant } from "../types/split";
import { centsToUsdString } from "../lib/money";

type Props = {
  currency: string;
  items: Item[];
  participants: Participant[];
  assignments: AssignmentsMap;
  onChange: (next: AssignmentsMap) => void;
  onBack?: () => void;
  onNext?: () => Promise<void> | void;
};

function unique(arr: string[]) {
  return Array.from(new Set(arr));
}

export default function Assignments({ currency, items, participants, assignments, onChange, onBack, onNext }: Props) {
  const [showErrors, setShowErrors] = useState(false);
  const [topError, setTopError] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const participantIds = useMemo(() => new Set(participants.map((p) => p.id)), [participants]);

  const normalizedAssignments = useMemo(() => {
    const next: AssignmentsMap = {};
    for (const it of items) {
      const raw = assignments[it.id] ?? [];
      next[it.id] = unique(raw.filter((pid) => participantIds.has(pid)));
    }
    return next;
  }, [assignments, items, participantIds]);

  const errors = useMemo(() => {
    const e: Record<string, string> = {};
    for (const it of items) {
      if ((normalizedAssignments[it.id] ?? []).length === 0) e[it.id] = "Required";
    }
    return e;
  }, [items, normalizedAssignments]);

  function setItemSelection(itemId: string, nextSelected: string[]) {
    onChange({ ...normalizedAssignments, [itemId]: unique(nextSelected.filter((pid) => participantIds.has(pid))) });
  }

  return (
    <div className="card tableCard stack">
      <div>
        <h2 className="stepTitle">Step 4 — Assign items</h2>
        <div className="helper">Start with none selected for each item.</div>
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button className="btn" disabled={isSubmitting} onClick={() => onChange(Object.fromEntries(items.map((it) => [it.id, participants.map((p) => p.id)])))}>
          Select everyone for all items
        </button>
        <button className="btn" disabled={isSubmitting} onClick={() => onChange(Object.fromEntries(items.map((it) => [it.id, []])))}>
          Clear all selections
        </button>
      </div>

      {topError && <div className="alert">{topError}</div>}

      <div className="participantsPanel">
        {items.map((it) => {
          const selected = normalizedAssignments[it.id] ?? [];
          const isExpanded = expanded[it.id] ?? true;
          const countText = `${selected.length} selected`;
          return (
            <div className="assignItem" key={it.id} ref={(el) => { itemRefs.current[it.id] = el; }}>
              <button className="assignHeader btn" disabled={isSubmitting} onClick={() => setExpanded((prev) => ({ ...prev, [it.id]: !isExpanded }))}>
                <div style={{ textAlign: "left" }}>{it.description || "(No description)"}</div>
                <div>{centsToUsdString(it.price_cents)} {currency}</div>
                <span className={selected.length === 0 ? "badgeWarning" : "badgeNeutral"}>{countText}</span>
              </button>

              {isExpanded && (
                <>
                  <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    <button className="btn" disabled={isSubmitting} onClick={() => setItemSelection(it.id, participants.map((p) => p.id))}>All</button>
                    <button className="btn" disabled={isSubmitting} onClick={() => setItemSelection(it.id, [])}>None</button>
                  </div>

                  <div className="chipRow">
                    {participants.map((p) => {
                      const active = selected.includes(p.id);
                      return (
                        <button
                          key={p.id}
                          className={`chip ${active ? "chipActive" : ""}`}
                          disabled={isSubmitting}
                          onClick={async () => {
                            const next = active ? selected.filter((id) => id !== p.id) : [...selected, p.id];
                            setItemSelection(it.id, next);
                          }}
                        >
                          {p.name}
                        </button>
                      );
                    })}
                  </div>

                  {showErrors && errors[it.id] && <div className="errorText">Required</div>}
                </>
              )}
            </div>
          );
        })}
      </div>

      <div className="actionsFooter actionsFooterSticky">
        {onBack ? <button className="btn" onClick={onBack} disabled={isSubmitting}>Back</button> : <span />}
        {onNext && (
          <button
            className="btn btnPrimary"
            onClick={async () => {
              const missing = items.filter((it) => (normalizedAssignments[it.id] ?? []).length === 0);
              if (missing.length > 0) {
                setShowErrors(true);
                setTopError(`${missing.length} item${missing.length > 1 ? "s" : ""} need at least one person selected`);
                const first = missing[0]?.id;
                if (first) {
                  setExpanded((prev) => ({ ...prev, [first]: true }));
                  itemRefs.current[first]?.scrollIntoView({ behavior: "smooth", block: "center" });
                }
                return;
              }
              setTopError("");
              onChange(normalizedAssignments);
              setIsSubmitting(true);
              try {
                await onNext();
              } finally {
                setIsSubmitting(false);
              }
            }}
          >
            {isSubmitting ? "Saving…" : "Next"}
          </button>
        )}
      </div>
    </div>
  );
}
