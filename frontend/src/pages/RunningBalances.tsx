import { Fragment, useEffect, useMemo, useState } from "react";
import { getRunningBalances } from "../lib/api";
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const fetchRunningBalances = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await getRunningBalances(apiBase);
        if (!isActive) return;
        setParticipants(response.participants);
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

  const sortedParticipants = useMemo(
    () => [...participants].sort((a, b) => a.participant_name.localeCompare(b.participant_name)),
    [participants]
  );

  const allExpanded =
    sortedParticipants.length > 0 &&
    sortedParticipants.every((participant) => Boolean(expandedParticipantIds[participant.participant_id]));

  const setAllExpanded = (expanded: boolean) => {
    setExpandedParticipantIds(
      Object.fromEntries(sortedParticipants.map((participant) => [participant.participant_id, expanded]))
    );
  };

  return (
    <div className="app">
      <h1 className="h1">Running balances</h1>

      <div className="card tableCard stack">
        {!isLoading && !error && sortedParticipants.length > 0 && (
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button className="btn" type="button" onClick={() => setAllExpanded(!allExpanded)}>
              {allExpanded ? "Collapse all" : "Expand all"}
            </button>
          </div>
        )}

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
              const expanded = Boolean(expandedParticipantIds[participant.participant_id]);

              return (
                <div key={participant.participant_id} className="participantsPanel">
                  <div className="participantRow" style={{ borderTop: "none" }}>
                    <div className="row">
                      <strong>{participant.participant_name}</strong>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <strong>{centsToUsdString(participant.participant_total_cents)}</strong>
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
                    <div className="participantRow">
                      {participant.bills.length === 0 ? (
                        <div className="helper">No items yet</div>
                      ) : (
                        <table className="table" style={{ minWidth: 0 }}>
                          <thead>
                            <tr>
                              <th>Item contribution</th>
                              <th style={{ textAlign: "right" }}>Bill contribution</th>
                              <th style={{ textAlign: "right" }}>Participant contribution</th>
                            </tr>
                          </thead>
                          <tbody>
                            {participant.bills.map((bill) => (
                              <Fragment key={bill.receipt_id}>
                                <tr key={`${bill.receipt_id}-header`}>
                                  <td colSpan={3}><strong>{bill.bill_description}</strong></td>
                                </tr>
                                {bill.lines.map((line) => (
                                  <tr key={line.receipt_item_id}>
                                    <td>
                                      <div className="row" style={{ justifyContent: "space-between" }}>
                                        <span>{line.item_name}</span>
                                        <span>{centsToUsdString(line.contribution_cents)}</span>
                                      </div>
                                    </td>
                                    <td style={{ textAlign: "right" }} />
                                    <td style={{ textAlign: "right" }} />
                                  </tr>
                                ))}
                                <tr key={`${bill.receipt_id}-total`}>
                                  <td />
                                  <td style={{ textAlign: "right" }}><strong>{centsToUsdString(bill.bill_total_cents)}</strong></td>
                                  <td style={{ textAlign: "right" }} />
                                </tr>
                              </Fragment>
                            ))}
                            <tr>
                              <td />
                              <td />
                              <td style={{ textAlign: "right" }}><strong>{centsToUsdString(participant.participant_total_cents)}</strong></td>
                            </tr>
                          </tbody>
                        </table>
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
