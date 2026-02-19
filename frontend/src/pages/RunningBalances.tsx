import { useEffect, useState } from "react";
import { getRunningBalances, settleParticipantInFull } from "../lib/api";
import { centsToUsdString } from "../lib/money";
import type { RunningBalanceParticipant } from "../types/split";

type Props = {
  apiBase: string;
  onBackHome: () => void;
};

export default function RunningBalances({ apiBase, onBackHome }: Props) {
  const [participants, setParticipants] = useState<RunningBalanceParticipant[]>([]);
  const [expandedParticipantIds, setExpandedParticipantIds] = useState<Record<string, boolean>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [settlingParticipantId, setSettlingParticipantId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const fetchRunningBalances = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const balances = await getRunningBalances(apiBase);
        if (!isActive) return;
        setParticipants(balances);
      } catch (e: unknown) {
        if (!isActive) return;
        setError(e instanceof Error ? e.message : "Failed to fetch running balances.");
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void fetchRunningBalances();

    return () => {
      isActive = false;
    };
  }, [apiBase]);

  return (
    <div className="app">
      <h1 className="h1">Running balances</h1>

      <div className="card tableCard stack">
        {isLoading && <div className="helper">Loading participants…</div>}

        {error && (
          <div className="alert">
            <strong>Couldn’t fetch running balances.</strong>
            <div>{error}</div>
          </div>
        )}

        {!isLoading && !error && (
          <div className="stack">
            {participants.length === 0 && <div className="helper">No outstanding balances.</div>}

            {participants.map((participant) => {
              const expanded = Boolean(expandedParticipantIds[participant.participant_id]);

              return (
                <div key={participant.participant_id} className="participantsPanel">
                  <div className="participantRow" style={{ borderTop: "none" }}>
                    <div className="row">
                      <strong>{participant.participant_name}</strong>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <strong>{centsToUsdString(participant.outstanding_total_cents)}</strong>
                        <button
                          className="btn"
                          type="button"
                          onClick={() => {
                            setExpandedParticipantIds((prev) => ({
                              ...prev,
                              [participant.participant_id]: !prev[participant.participant_id],
                            }));
                          }}
                          aria-expanded={expanded}
                          aria-label={`${expanded ? "Collapse" : "Expand"} ${participant.participant_name} ledger`}
                        >
                          {expanded ? "▾" : "▸"}
                        </button>
                      </div>
                    </div>
                  </div>

                  {expanded && (
                    <div className="participantRow stack">
                      {participant.bills.length === 0 ? (
                        <div className="helper">No items yet</div>
                      ) : (
                        <div className="stack">
                          {participant.bills.map((bill) => (
                            <div key={bill.receipt_id} className="stack">
                              <div className="row">
                                <strong>{bill.bill_description}</strong>
                                <strong>{centsToUsdString(bill.bill_total_cents)}</strong>
                              </div>
                              <table className="table" style={{ minWidth: 0 }}>
                                <thead>
                                  <tr>
                                    <th>Item</th>
                                    <th style={{ textAlign: "right" }}>Contribution</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {bill.lines.map((line) => (
                                    <tr key={line.receipt_item_id}>
                                      <td>{line.item_name}</td>
                                      <td style={{ textAlign: "right" }}>{centsToUsdString(line.contribution_cents)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="row" style={{ justifyContent: "flex-end" }}>
                        <button
                          className="btn"
                          type="button"
                          disabled={settlingParticipantId === participant.participant_id}
                          onClick={async () => {
                            try {
                              setError(null);
                              setSettlingParticipantId(participant.participant_id);
                              await settleParticipantInFull({
                                participantId: participant.participant_id,
                                amount_cents: participant.outstanding_total_cents,
                                apiBase,
                              });
                              setParticipants((prev) =>
                                prev.filter((p) => p.participant_id !== participant.participant_id)
                              );
                            } catch (e: unknown) {
                              setError(e instanceof Error ? e.message : "Failed to settle participant.");
                            } finally {
                              setSettlingParticipantId(null);
                            }
                          }}
                        >
                          {settlingParticipantId === participant.participant_id
                            ? "Settling…"
                            : `Settle in full (${centsToUsdString(participant.outstanding_total_cents)})`}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="actionsFooter">
          <button className="btn" onClick={onBackHome}>Back to home</button>
        </div>
      </div>
    </div>
  );
}
