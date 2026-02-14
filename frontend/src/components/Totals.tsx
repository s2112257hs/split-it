import { useMemo } from "react";
import type { AssignmentsMap, Item, Participant } from "../types/split";
import { centsToUsdString } from "../lib/money";
import { computePennyPerfectSplit } from "../lib/pennySplit";

type Props = {
  currency: string;
  items: Item[];
  participants: Participant[];
  assignments: AssignmentsMap;
  onBack?: () => void;
  onReset?: () => void; // optional for later
};

export default function Totals({
  currency,
  items,
  participants,
  assignments,
  onBack,
  onReset,
}: Props) {
  const result = useMemo(() => {
    return computePennyPerfectSplit({ items, participants, assignments });
  }, [items, participants, assignments]);

  const sumPerPerson = useMemo(() => {
    return result.per_person.reduce((s, p) => s + p.total_cents, 0);
  }, [result.per_person]);

  const reconciles = sumPerPerson === result.assigned_total_cents;

  return (
    <div className="stack">
      <div>
        <h2 style={{ margin: 0 }}>Step 5 — Totals</h2>
        <div className="small" style={{ marginTop: 4 }}>
          Penny-perfect split in cents. Totals reconcile exactly.
        </div>
      </div>

      {result.unassigned_item_ids.length > 0 && (
        <div className="alert">
          <strong className="alertTitle">Unassigned items</strong>
          <div className="small" style={{ marginTop: 4 }}>
            {result.unassigned_item_ids.length} item(s) have no participants selected.
            Go back and assign at least one person per item.
          </div>
        </div>
      )}

      <div className="card stack">
        <div className="row" style={{ alignItems: "baseline" }}>
          <div style={{ fontWeight: 800 }}>Per-person totals</div>
          <div className="small">Currency: {currency}</div>
        </div>

        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Person</th>
                <th style={{ textAlign: "right" }}>Total ({currency})</th>
              </tr>
            </thead>
            <tbody>
              {result.per_person.map((p) => (
                <tr key={p.participant_id}>
                  <td>{p.participant_name}</td>
                  <td style={{ textAlign: "right" }}>{centsToUsdString(p.total_cents)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>Sum</td>
                <td style={{ textAlign: "right" }}>{centsToUsdString(sumPerPerson)}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div className="card stack" style={{ boxShadow: "none" }}>
          <div className="row">
            <div className="small">Receipt total (all items)</div>
            <div style={{ fontWeight: 700 }}>{centsToUsdString(result.receipt_total_cents)} {currency}</div>
          </div>
          <div className="row">
            <div className="small">Assigned items total</div>
            <div style={{ fontWeight: 700 }}>{centsToUsdString(result.assigned_total_cents)} {currency}</div>
          </div>
          <div className="row">
            <div className="small">Per-person sum</div>
            <div style={{ fontWeight: 700 }}>{centsToUsdString(sumPerPerson)} {currency}</div>
          </div>

          <div className="small" style={{ marginTop: 6 }}>
            Reconciliation:{" "}
            <span style={{ fontWeight: 800 }}>
              {reconciles ? "OK" : "Mismatch"}
            </span>
          </div>
        </div>
      </div>

      <div className="row">
        {onBack && (
          <button className="btn" onClick={onBack}>
            Back
          </button>
        )}
        {onReset && (
          <button className="btn" onClick={onReset}>
            Start over
          </button>
        )}
      </div>
    </div>
  );
}
