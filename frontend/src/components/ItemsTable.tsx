import { useEffect, useMemo, useState } from "react";
import { centsToUsdString, usdStringToCents } from "../lib/money";

export type Item = {
  id: string;
  description: string;
  price_cents: number;
};

type Props = {
  currency: string;
  items: Item[];
  onChange: (next: Item[]) => void;
  onBack?: () => void;
  onNext?: () => void;
};

function makeLocalId() {
  return `item_${crypto.randomUUID()}`;
}

export default function ItemsTable({ currency, items, onChange, onBack, onNext }: Props) {
  const [priceDraft, setPriceDraft] = useState<Record<string, string>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  // Keep drafts in sync with items (after OCR / add/delete)
  useEffect(() => {
    setPriceDraft((prev) => {
      const next: Record<string, string> = { ...prev };
      for (const it of items) {
        if (next[it.id] == null) next[it.id] = centsToUsdString(it.price_cents);
      }
      for (const id of Object.keys(next)) {
        if (!items.some((it) => it.id === id)) delete next[id];
      }
      return next;
    });
  }, [items]);

  const totalCents = useMemo(
    () => items.reduce((sum, it) => sum + (Number.isFinite(it.price_cents) ? it.price_cents : 0), 0),
    [items]
  );

  function setItem(id: string, patch: Partial<Item>) {
    onChange(items.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  }

  function removeItem(id: string) {
    onChange(items.filter((it) => it.id !== id));
    setPriceDraft((prev) => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
    setRowErrors((prev) => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
    setTouched((prev) => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
  }

  function addItem() {
    const id = makeLocalId();
    onChange([...items, { id, description: "", price_cents: 0 }]);
    setPriceDraft((prev) => ({ ...prev, [id]: "0.00" }));
    setTouched((prev) => ({ ...prev, [id]: false }));
  }

  function setRowError(id: string, msg: string | null) {
    setRowErrors((prev) => {
      const copy = { ...prev };
      if (!msg) delete copy[id];
      else copy[id] = msg;
      return copy;
    });
  }

  /** Validate a single draft string. If valid -> commit to price_cents immediately. */
  function validateAndCommitOne(id: string, raw: string) {
    try {
      const cents = usdStringToCents(raw);
      // Commit immediately so Total updates instantly
      setItem(id, { price_cents: cents });
      setRowError(id, null);
    } catch (e: any) {
      setRowError(id, e?.message ?? "Invalid price");
      // Do NOT change price_cents when invalid; total stays based on last valid value.
    }
  }

  /** On Next, we force-validation on all rows (including untouched/empty). */
  function validateAllForNext(): boolean {
    const errors: Record<string, string> = {};

    for (const it of items) {
      const raw = (priceDraft[it.id] ?? "").trim();
      try {
        const cents = usdStringToCents(raw);
        // Ensure items state matches drafts before proceeding
        if (it.price_cents !== cents) {
          // commit
          setItem(it.id, { price_cents: cents });
        }
      } catch (e: any) {
        errors[it.id] = e?.message ?? "Invalid price";
      }
    }

    setRowErrors(errors);
    // mark all touched so errors display
    setTouched((prev) => {
      const next = { ...prev };
      for (const it of items) next[it.id] = true;
      return next;
    });

    return Object.keys(errors).length === 0;
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div>
        <h2 style={{ margin: 0 }}>Step 2 — Verify items</h2>
        <div style={{ opacity: 0.75, marginTop: 4 }}>
          Edit descriptions and prices. Total updates immediately when the price becomes valid.
        </div>
      </div>

      <div style={{ overflowX: "auto", border: "1px solid #ddd", borderRadius: 12 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 640 }}>
          <thead>
            <tr style={{ background: "#f6f6f6" }}>
              <th style={th}>Description</th>
              <th style={{ ...th, width: 180, textAlign: "right" }}>Price ({currency})</th>
              <th style={{ ...th, width: 110 }}></th>
            </tr>
          </thead>

          <tbody>
            {items.map((it) => {
              const err = rowErrors[it.id];
              const showErr = touched[it.id] && !!err;

              return (
                <tr key={it.id} style={{ borderTop: "1px solid #eee" }}>
                  <td style={td}>
                    <input
                      value={it.description}
                      placeholder="e.g., Burger"
                      onChange={(e) => setItem(it.id, { description: e.target.value })}
                      style={input}
                    />
                  </td>

                  <td style={{ ...td, textAlign: "right" }}>
                    <input
                      value={priceDraft[it.id] ?? ""}
                      inputMode="decimal"
                      placeholder="0.00"
                      onChange={(e) => {
                        const nextRaw = e.target.value;
                        setPriceDraft((prev) => ({ ...prev, [it.id]: nextRaw }));
                        setTouched((prev) => ({ ...prev, [it.id]: true }));
                        // Validate immediately and commit if valid
                        validateAndCommitOne(it.id, nextRaw);
                      }}
                      onBlur={() => {
                        // Normalize if valid (e.g., "12." -> "12.00")
                        const raw = (priceDraft[it.id] ?? "").trim();
                        try {
                          const cents = usdStringToCents(raw);
                          setPriceDraft((prev) => ({ ...prev, [it.id]: centsToUsdString(cents) }));
                          setItem(it.id, { price_cents: cents });
                          setRowError(it.id, null);
                        } catch {
                          // keep as-is; error already shown if touched
                        }
                      }}
                      style={{
                        ...input,
                        textAlign: "right",
                        borderColor: showErr ? "#b00020" : input.borderColor,
                      }}
                    />
                    {showErr && (
                      <div style={{ marginTop: 6, color: "#b00020", fontSize: 12, textAlign: "left" }}>
                        {err}
                      </div>
                    )}
                  </td>

                  <td style={{ ...td, textAlign: "right" }}>
                    <button onClick={() => removeItem(it.id)} style={dangerBtn}>
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}

            {items.length === 0 && (
              <tr>
                <td style={td} colSpan={3}>
                  No items yet. Click “Add item”.
                </td>
              </tr>
            )}
          </tbody>

          <tfoot>
            <tr style={{ borderTop: "1px solid #eee", background: "#fafafa" }}>
              <td style={{ ...td, fontWeight: 700 }}>Total</td>
              <td style={{ ...td, textAlign: "right", fontWeight: 700 }}>
                {centsToUsdString(totalCents)}
              </td>
              <td style={td}></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div style={{ display: "flex", gap: 10, justifyContent: "space-between", alignItems: "center" }}>
        <button onClick={addItem} style={btn}>
          + Add item
        </button>

        <div style={{ display: "flex", gap: 10 }}>
          {onBack && (
            <button onClick={onBack} style={btn}>
              Back
            </button>
          )}
          {onNext && (
            <button
              onClick={() => {
                const ok = validateAllForNext();
                if (ok) onNext();
              }}
              style={primaryBtn}
            >
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "12px 12px",
  fontSize: 13,
  letterSpacing: 0.2,
  borderBottom: "1px solid #e8e8e8",
};

const td: React.CSSProperties = {
  padding: "10px 12px",
  verticalAlign: "top",
};

const input: React.CSSProperties = {
  width: "100%",
  padding: "9px 10px",
  borderRadius: 10,
  border: "1px solid #ccc",
  outline: "none",
  fontSize: 14,
};

const btn: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #222",
  background: "#fff",
  cursor: "pointer",
};

const primaryBtn: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #111",
  background: "#111",
  color: "#fff",
  cursor: "pointer",
};

const dangerBtn: React.CSSProperties = {
  padding: "8px 10px",
  borderRadius: 10,
  border: "1px solid #b00020",
  background: "#fff",
  color: "#b00020",
  cursor: "pointer",
};
