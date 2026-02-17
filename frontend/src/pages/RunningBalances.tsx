import { useEffect, useMemo, useState } from "react";
import { getParticipantLedger, listParticipants } from "../lib/api";
import { centsToUsdString } from "../lib/money";
import type { Participant, ParticipantLedger } from "../types/split";

type Props = {
  apiBase: string;
  onBackHome: () => void;
};

export default function RunningBalances({ apiBase, onBackHome }: Props) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [ledgersByParticipantId, setLedgersByParticipantId] = useState<Record<string, ParticipantLedger>>({});
  const [expandedParticipantIds, setExpandedParticipantIds] = useState<Record<string, boolean>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const fetchParticipantsAndLedgers = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const participantList = await listParticipants(apiBase);
        if (!isActive) return;

        const ledgers = await Promise.all(
          participantList.map(async (participant) => {
            const ledger = await getParticipantLedger({ participantId: participant.id, apiBase });
            return [participant.id, ledger] as const;
          })
        );

        if (!isActive) return;

        setParticipants(participantList);
        setLedgersByParticipantId(Object.fromEntries(ledgers));
      } catch (e: unknown) {
        if (!isActive) return;
        setError(e instanceof Error ? e.message : "Failed to fetch running balances.");
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void fetchParticipantsAndLedgers();

    return () => {
      isActive = false;
    };
  }, [apiBase]);

  const sortedParticipants = useMemo(
    () => [...participants].sort((a, b) => a.display_name.localeCompare(b.display_name)),
    [participants]
  );

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
            {sortedParticipants.map((participant) => {
              const ledger = ledgersByParticipantId[participant.id];
              const expanded = Boolean(expandedParticipantIds[participant.id]);

              return (
                <div key={participant.id} className="participantsPanel">
                  <div className="participantRow" style={{ borderTop: "none" }}>
                    <div className="row">
                      <strong>{participant.display_name}</strong>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <strong>{centsToUsdString(ledger?.computed_total_cents ?? 0)}</strong>
                        <button
                          className="btn"
                          type="button"
                          onClick={() => {
                            setExpandedParticipantIds((prev) => ({
                              ...prev,
                              [participant.id]: !prev[participant.id],
                            }));
                          }}
                          aria-expanded={expanded}
                          aria-label={`${expanded ? "Collapse" : "Expand"} ${participant.display_name} ledger`}
                        >
                          {expanded ? "▾" : "▸"}
                        </button>
                      </div>
                    </div>
                  </div>

                  {expanded && (
                    <div className="participantRow">
                      {!ledger || ledger.bills.length === 0 ? (
                        <div className="helper">No items yet</div>
                      ) : (
                        <div className="stack">
                          {ledger.bills.map((bill) => (
                            <div key={bill.receipt_image_id} className="stack">
                              <strong>{bill.bill_description}</strong>
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
                                      <td>{line.item_description}</td>
                                      <td style={{ textAlign: "right" }}>{centsToUsdString(line.amount_cents)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ))}
                        </div>
                      )}
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
