import { useEffect, useMemo, useState } from "react";
import { getSummary } from "../lib/api";
import { centsToUsdString } from "../lib/money";
import type { Participant } from "../types/split";

type Props = {
  apiBase: string;
  receiptImageId: string;
  currency: string;
  items: Array<{ id: string; description: string; price_cents: number }>;
  participants: Participant[];
  onBack?: () => void;
  onReset?: () => void;
};

export default function Totals({ apiBase, receiptImageId, currency, items, participants, onBack, onReset }: Props) {
  const [copied, setCopied] = useState(false);
  const [totalsByParticipantId, setTotalsByParticipantId] = useState<Record<string, number>>({});
  const [assignedTotalCents, setAssignedTotalCents] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const receiptTotalCents = useMemo(() => items.reduce((sum, item) => sum + item.price_cents, 0), [items]);

  useEffect(() => {
    let isActive = true;

    const fetchSummary = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const result = await getSummary({
          receiptImageId,
          participantIds: participants.map((participant) => participant.id),
          apiBase,
        });

        if (!isActive) return;
        setTotalsByParticipantId(result.totals_by_participant_id);
        setAssignedTotalCents(result.grand_total_cents);
      } catch (e: unknown) {
        if (!isActive) return;
        setError(e instanceof Error ? e.message : "Failed to fetch summary.");
      } finally {
        if (isActive) setIsLoading(false);
      }
    };

    void fetchSummary();

    return () => {
      isActive = false;
    };
  }, [receiptImageId, participants, apiBase]);

  const sumPerPerson = useMemo(
    () => participants.reduce((sum, participant) => sum + (totalsByParticipantId[participant.id] ?? 0), 0),
    [participants, totalsByParticipantId]
  );

  const reconciles = sumPerPerson === assignedTotalCents;

  return (
    <div className="card tableCard stack">
      <div>
        <h2 className="stepTitle">Totals</h2>
      </div>

      <div className="pillRow">
        <div className="pill">Receipt total: {centsToUsdString(receiptTotalCents)} {currency}</div>
        <div className="pill">Assigned total: {centsToUsdString(assignedTotalCents)} {currency}</div>
        <div className={reconciles ? "statusOk" : "statusBad"}>{reconciles ? "OK" : "Mismatch"}</div>
      </div>

      {isLoading && <div className="helper">Loading summary…</div>}

      {error && (
        <div className="alert">
          <strong>Couldn’t load summary.</strong>
          <div>{error}</div>
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
            {participants.map((participant) => (
              <tr key={participant.id}>
                <td>{participant.name}</td>
                <td style={{ textAlign: "right" }}>{centsToUsdString(totalsByParticipantId[participant.id] ?? 0)}</td>
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
            const lines = participants.map(
              (participant) => `${participant.name} — ${centsToUsdString(totalsByParticipantId[participant.id] ?? 0)} ${currency}`
            );
            lines.push(`Total — ${centsToUsdString(assignedTotalCents)} ${currency}`);
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
