import { Fragment, useMemo, useState } from "react";
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
  const [expandedPeople, setExpandedPeople] = useState<Record<string, boolean>>({});

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
            {result.per_person.map((p) => {
              const isExpanded = expandedPeople[p.participant_id] ?? false;

              return (
                <Fragment key={p.participant_id}>
                  <tr key={p.participant_id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "space-between" }}>
                        <span>{p.participant_name}</span>
                        <button
                          className="btn"
                          style={{ minHeight: 30, fontSize: 13, padding: "0 10px" }}
                          onClick={() => {
                            setExpandedPeople((prev) => ({
                              ...prev,
                              [p.participant_id]: !isExpanded,
                            }));
                          }}
                        >
                          {isExpanded ? "Hide details" : "View details"}
                        </button>
                      </div>
                    </td>
                    <td style={{ textAlign: "right" }}>{centsToUsdString(p.total_cents)}</td>
                  </tr>
                  {isExpanded && (
                    <tr key={`${p.participant_id}-details`}>
                      <td colSpan={2} style={{ background: "rgba(255, 255, 255, 0.02)" }}>
                        {p.items.length === 0 ? (
                          <div className="helper">No items assigned.</div>
                        ) : (
                          <div className="stack" style={{ gap: 6 }}>
                            {p.items.map((item) => (
                              <div key={`${p.participant_id}-${item.item_id}`} className="row" style={{ alignItems: "flex-start" }}>
                                <span>{item.item_name}</span>
                                <strong>{centsToUsdString(item.amount_cents)} {currency}</strong>
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
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
