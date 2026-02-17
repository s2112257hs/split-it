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

const MIN_QTY = 1;
const MAX_QTY = 99;

function makeLocalId() {
  return `item_${crypto.randomUUID()}`;
}

export default function ItemsTable({ currency, items, onChange, onBack, onNext }: Props) {
  const [priceDraft, setPriceDraft] = useState<Record<string, string>>({});
  const [qtyDraft, setQtyDraft] = useState<Record<string, string>>({});
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
    setQtyDraft((prev) => {
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
    onChange([...items, { id, description: "", price_cents: 0, quantity: 1 }]);
    setPriceDraft((prev) => ({ ...prev, [id]: "0.00" }));
    setQtyDraft((prev) => ({ ...prev, [id]: "1" }));
  }

  function setRowError(id: string, msg: string | null) {
    setRowErrors((prev) => {
      const copy = { ...prev };
      if (!msg) delete copy[id];
      else copy[id] = msg;
      return copy;
    });
  }

  function validatePrice(raw: string): number {
    return usdStringToCents(raw);
  }

  function validateQty(raw: string): number {
    const trimmed = raw.trim();
    if (!/^\d+$/.test(trimmed)) {
      throw new Error("Quantity must be a whole number");
    }

    const qty = Number.parseInt(trimmed, 10);
    if (qty < MIN_QTY || qty > MAX_QTY) {
      throw new Error(`Quantity must be between ${MIN_QTY} and ${MAX_QTY}`);
    }

    return qty;
  }

  function validateAndCommitPrice(id: string, raw: string) {
    try {
      const cents = validatePrice(raw);
      setItem(id, { price_cents: cents });
      setRowError(id, null);
    } catch (e: unknown) {
      setRowError(id, e instanceof Error ? e.message : "Invalid price");
    }
  }

  function validateAndCommitQty(id: string, raw: string) {
    try {
      const quantity = validateQty(raw);
      setItem(id, { quantity });
      setRowError(id, null);
    } catch (e: unknown) {
      setRowError(id, e instanceof Error ? e.message : "Invalid quantity");
    }
  }

  function validateAllForNext(): boolean {
    const errors: Record<string, string> = {};

    for (const it of items) {
      const priceRaw = (priceDraft[it.id] ?? centsToUsdString(it.price_cents)).trim();
      try {
        const cents = validatePrice(priceRaw);
        if (it.price_cents !== cents) setItem(it.id, { price_cents: cents });
      } catch (e: unknown) {
        errors[it.id] = e instanceof Error ? e.message : "Invalid price";
        continue;
      }

      const qtyRaw = (qtyDraft[it.id] ?? String(it.quantity)).trim();
      try {
        const quantity = validateQty(qtyRaw);
        if (it.quantity !== quantity) setItem(it.id, { quantity });
      } catch (e: unknown) {
        errors[it.id] = e instanceof Error ? e.message : "Invalid quantity";
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
          <div className="helper">Fix names, prices, and quantities</div>
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
          Fix {errorCount} invalid row{errorCount > 1 ? "s" : ""} to continue
        </button>
      )}

      <div className="tableWrap">
        <table className="table">
          <thead>
            <tr>
              <th>Description</th>
              <th style={{ width: 140, textAlign: "right" }}>Price ({currency})</th>
              <th style={{ width: 100 }}>Qty</th>
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
                        validateAndCommitPrice(it.id, nextRaw);
                      }}
                      onBlur={() => {
                        const raw = (priceDraft[it.id] ?? centsToUsdString(it.price_cents)).trim();
                        try {
                          const cents = validatePrice(raw);
                          setPriceDraft((prev) => ({ ...prev, [it.id]: centsToUsdString(cents) }));
                          setItem(it.id, { price_cents: cents });
                          setRowError(it.id, null);
                        } catch {
                          // Keep invalid string to allow user edits.
                        }
                      }}
                    />
                  </td>
                  <td>
                    <input
                      className={`input ${err ? "inputError" : ""}`}
                      value={qtyDraft[it.id] ?? String(it.quantity)}
                      inputMode="numeric"
                      placeholder="1"
                      min={MIN_QTY}
                      max={MAX_QTY}
                      onChange={(e) => {
                        const nextRaw = e.target.value;
                        setQtyDraft((prev) => ({ ...prev, [it.id]: nextRaw }));
                        validateAndCommitQty(it.id, nextRaw);
                      }}
                      onBlur={() => {
                        const raw = (qtyDraft[it.id] ?? String(it.quantity)).trim();
                        try {
                          const quantity = validateQty(raw);
                          setQtyDraft((prev) => ({ ...prev, [it.id]: String(quantity) }));
                          setItem(it.id, { quantity });
                          setRowError(it.id, null);
                        } catch {
                          // Keep invalid string to allow user edits.
                        }
                      }}
                    />
                    {err && <div className="errorText">{err}</div>}
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
