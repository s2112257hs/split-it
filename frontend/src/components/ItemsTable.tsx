import { useMemo, useRef, useState } from "react";
import { centsToUsdString, usdStringToCents } from "../lib/money";
import type { Item } from "../types/split";

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
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

  const totalCents = useMemo(
    () => items.reduce((sum, it) => sum + (Number.isFinite(it.price_cents) ? it.price_cents : 0), 0),
    [items]
  );

  const errorCount = Object.keys(rowErrors).length;

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
  }

  function addItem() {
    const id = makeLocalId();
    onChange([...items, { id, description: "", price_cents: 0 }]);
    setPriceDraft((prev) => ({ ...prev, [id]: "0.00" }));
  }

  function setRowError(id: string, msg: string | null) {
    setRowErrors((prev) => {
      const copy = { ...prev };
      if (!msg) delete copy[id];
      else copy[id] = msg;
      return copy;
    });
  }

  function validateAndCommitOne(id: string, raw: string) {
    try {
      const cents = usdStringToCents(raw);
      setItem(id, { price_cents: cents });
      setRowError(id, null);
    } catch (e: unknown) {
      setRowError(id, e instanceof Error ? e.message : "Invalid price");
    }
  }

  function validateAllForNext(): boolean {
    const errors: Record<string, string> = {};

    for (const it of items) {
      const raw = (priceDraft[it.id] ?? centsToUsdString(it.price_cents)).trim();
      try {
        const cents = usdStringToCents(raw);
        if (it.price_cents !== cents) setItem(it.id, { price_cents: cents });
      } catch (e: unknown) {
        errors[it.id] = e instanceof Error ? e.message : "Invalid price";
      }
    }

    setRowErrors(errors);

    const firstInvalid = Object.keys(errors)[0];
    if (firstInvalid) {
      rowRefs.current[firstInvalid]?.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    return Object.keys(errors).length === 0;
  }

  return (
    <div className="card tableCard stack">
      <div className="row">
        <div>
          <h2 className="stepTitle">Step 2 — Verify items</h2>
          <div className="helper">Fix names & prices</div>
        </div>
        <div className="pill">Total: {centsToUsdString(totalCents)} {currency}</div>
      </div>

      {errorCount > 0 && (
        <button
          className="alert"
          onClick={() => {
            const firstInvalid = Object.keys(rowErrors)[0];
            if (firstInvalid) rowRefs.current[firstInvalid]?.scrollIntoView({ behavior: "smooth", block: "center" });
          }}
        >
          Fix {errorCount} invalid price{errorCount > 1 ? "s" : ""} to continue
        </button>
      )}

      <div className="tableWrap">
        <table className="table">
          <thead>
            <tr>
              <th>Description</th>
              <th style={{ width: 140, textAlign: "right" }}>Price ({currency})</th>
              <th style={{ width: 90 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => {
              const err = rowErrors[it.id];
              return (
                <tr key={it.id} ref={(el) => { rowRefs.current[it.id] = el; }}>
                  <td>
                    <input
                      className="input"
                      value={it.description}
                      placeholder="e.g., Burger"
                      onChange={(e) => setItem(it.id, { description: e.target.value })}
                    />
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <input
                      className={`input ${err ? "inputError" : ""}`}
                      style={{ textAlign: "right" }}
                      value={priceDraft[it.id] ?? centsToUsdString(it.price_cents)}
                      inputMode="decimal"
                      placeholder="0.00"
                      onChange={(e) => {
                        const nextRaw = e.target.value;
                        setPriceDraft((prev) => ({ ...prev, [it.id]: nextRaw }));
                        validateAndCommitOne(it.id, nextRaw);
                      }}
                      onBlur={() => {
                        const raw = (priceDraft[it.id] ?? centsToUsdString(it.price_cents)).trim();
                        try {
                          const cents = usdStringToCents(raw);
                          setPriceDraft((prev) => ({ ...prev, [it.id]: centsToUsdString(cents) }));
                          setItem(it.id, { price_cents: cents });
                          setRowError(it.id, null);
                        } catch {
                          // Keep invalid string to allow user edits.
                        }
                      }}
                    />
                    {err && <div className="errorText" style={{ textAlign: "left" }}>{err}</div>}
                  </td>
                  <td>
                    <button className="btn btnDanger" onClick={() => removeItem(it.id)}>Delete</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <button className="btn" onClick={addItem} style={{ width: "fit-content" }}>+ Add item</button>

      <div className="actionsFooter actionsFooterSticky">
        {onBack ? <button className="btn" onClick={onBack}>Back</button> : <span />}
        {onNext && (
          <button
            className="btn btnPrimary"
            onClick={() => {
              const ok = validateAllForNext();
              if (ok) onNext();
            }}
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}
