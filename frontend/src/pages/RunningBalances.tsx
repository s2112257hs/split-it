import { Fragment, useEffect, useMemo, useState } from "react";
import { getRunningBalances } from "../lib/api";
import { centsToUsdString } from "../lib/money";
import type { RunningBalanceParticipant } from "../types/split";

type Props = {
  apiBase: string;
  onBackHome: () => void;
};

function formatEventAt(isoDateTime: string): string {
  const d = new Date(isoDateTime);
  if (Number.isNaN(d.getTime())) return isoDateTime;
  return d.toLocaleString();
}

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

  const participantsWithDetails = useMemo(
    () =>
      sortedParticipants.filter(
        (participant) => participant.status !== "settled" && participant.net_balance_cents !== 0
      ),
    [sortedParticipants]
  );

  const allExpanded =
    participantsWithDetails.length > 0 &&
    participantsWithDetails.every((participant) => Boolean(expandedParticipantIds[participant.participant_id]));

  const setAllExpanded = (expanded: boolean) => {
    setExpandedParticipantIds(
      Object.fromEntries(participantsWithDetails.map((participant) => [participant.participant_id, expanded]))
    );
  };

  return (
    <div className="app">
      <h1 className="h1">Running balances</h1>

      <div className="card tableCard stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <button className="btn" onClick={onBackHome}>Back to home</button>
          {!isLoading && !error && participantsWithDetails.length > 0 && (
            <button className="btn" type="button" onClick={() => setAllExpanded(!allExpanded)}>
              {allExpanded ? "Collapse all" : "Expand all"}
            </button>
          )}
        </div>

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
              const canShowDetails =
                participant.status !== "settled" && participant.net_balance_cents !== 0;
              const billsTotalCents = participant.bills.reduce(
                (sum, bill) => sum + bill.bill_total_cents,
                0
              );
              const paymentsReceivedCents = participant.settlement_events.reduce(
                (sum, event) => sum + event.amount_cents,
                0
              );
              const repaymentsSentCents = participant.repayment_events.reduce(
                (sum, event) => sum + event.amount_cents,
                0
              );

              return (
                <div key={participant.participant_id} className="participantsPanel">
                  <div className="participantRow" style={{ borderTop: "none" }}>
                    <div className="row">
                      <strong>{participant.participant_name}</strong>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <strong>{centsToUsdString(participant.participant_total_cents)}</strong>
                        {canShowDetails ? (
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
                        ) : (
                          <span className="statusOk">settled</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {canShowDetails && expanded && (
                    <div className="participantRow">
                      {participant.bills.length === 0 &&
                      participant.settlement_events.length === 0 &&
                      participant.repayment_events.length === 0 ? (
                        <div className="helper">No activity in current cycle.</div>
                      ) : (
                        <>
                          <div className="helper">Showing activity since last settled point.</div>

                          {participant.bills.length > 0 && (
                            <table className="table" style={{ minWidth: 0 }}>
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
                                      <td>
                                        <strong><span>Bill Total</span></strong>
                                      </td>
                                      <td style={{ textAlign: "right" }} />
                                      <td style={{ textAlign: "right" }}><strong>{centsToUsdString(bill.bill_total_cents)}</strong></td>
                                    </tr>
                                  </Fragment>
                                ))}
                              </tbody>
                            </table>
                          )}


                          {participant.repayment_events.length > 0 && (
                            <div className="stack">
                              <div className="helper">Repayments you made to participant</div>
                              <table className="table" style={{ minWidth: 0 }}>
                                <thead>
                                  <tr>
                                    <th>Date</th>
                                    <th>Details</th>
                                    <th style={{ textAlign: "right" }}>Amount</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {participant.repayment_events.map((event) => (
                                    <tr key={event.event_id}>
                                      <td>{formatEventAt(event.event_at)}</td>
                                      <td>{event.reference_details}</td>
                                      <td style={{ textAlign: "right" }}>{centsToUsdString(event.amount_cents)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          <table className="table" style={{ minWidth: 0 }}>
                            <tbody>
                              <tr>
                                <td><strong>Bills total</strong></td>
                                <td />
                                <td style={{ textAlign: "right" }}><strong>{centsToUsdString(billsTotalCents)}</strong></td>
                              </tr>
                              <tr>
                                <td><strong>Payments received from {participant.participant_name}</strong></td>
                                <td />
                                <td style={{ textAlign: "right" }}><strong>{centsToUsdString(paymentsReceivedCents)}</strong></td>
                              </tr>
                              <tr>
                                <td><strong>Repayments sent to {participant.participant_name}</strong></td>
                                <td />
                                <td style={{ textAlign: "right" }}><strong>{centsToUsdString(repaymentsSentCents)}</strong></td>
                              </tr>
                            </tbody>
                          </table>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
