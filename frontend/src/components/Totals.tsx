import { useMemo, useState } from "react";
import type { AssignmentsMap, Item, Participant } from "../types/split";
import { centsToUsdString } from "../lib/money";
import { computePennyPerfectSplit } from "../lib/pennySplit";

type Props = {
  currency: string;
  items: Item[];
  participants: Participant[];
  assignments: AssignmentsMap;
  onBack?: () => void;
  onReset?: () => void;
};

export default function Totals({ currency, items, participants, assignments, onBack, onReset }: Props) {
  const [copied, setCopied] = useState(false);

  const result = useMemo(
    () => computePennyPerfectSplit({ items, participants, assignments }),
    [items, participants, assignments]
  );

  const sumPerPerson = useMemo(
    () => result.per_person.reduce((s, p) => s + p.total_cents, 0),
    [result.per_person]
  );

  const reconciles = sumPerPerson === result.assigned_total_cents;

  return (
    <div className="card tableCard stack">
      <div>
        <h2 className="stepTitle">Totals</h2>
      </div>

      <div className="pillRow">
        <div className="pill">Receipt total: {centsToUsdString(result.receipt_total_cents)} {currency}</div>
        <div className="pill">Assigned total: {centsToUsdString(result.assigned_total_cents)} {currency}</div>
        <div className={reconciles ? "statusOk" : "statusBad"}>{reconciles ? "OK" : "Mismatch"}</div>
      </div>

      {result.unassigned_item_ids.length > 0 && (
        <div className="alert">
          <strong>Unassigned items exist.</strong>
          <div style={{ marginTop: 8 }}>
            <button className="btn btnDanger" onClick={onBack}>Go back to assignments</button>
          </div>
        </div>
      )}

      <div className="tableWrap">
        <table className="table" style={{ minWidth: 0 }}>
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

      <div className="card stack">
        <button
          className="btn"
          onClick={async () => {
            const lines = result.per_person.map((p) => `${p.participant_name} — ${centsToUsdString(p.total_cents)} ${currency}`);
            lines.push(`Total — ${centsToUsdString(result.assigned_total_cents)} ${currency}`);
            await navigator.clipboard.writeText(lines.join("\n"));
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          Copy summary
        </button>
        {copied && <div className="helper">Copied to clipboard</div>}
      </div>

      <div className="actionsFooter actionsFooterSticky">
        {onBack ? <button className="btn" onClick={onBack}>Back</button> : <span />}
        {onReset && <button className="btn" onClick={onReset}>Start over</button>}
      </div>
    </div>
  );
}
