import { useEffect, useMemo, useState } from "react";
import { getParticipantLedger, listParticipants } from "../lib/api";
import { centsToUsdString } from "../lib/money";
import type { Participant, ParticipantLedger } from "../types/split";

const CSV_HEADERS = ["participant_name", "bill_description", "item_name", "contribution_usd"];

function escapeCsvField(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replaceAll('"', '""')}"`;
  }
  return value;
}

function formatUsdFromCents(cents: number): string {
  return (cents / 100).toFixed(2);
}

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

  const handleExportCsv = () => {
    const rows: string[] = [CSV_HEADERS.join(",")];
    let grandTotalCents = 0;

    for (const participant of sortedParticipants) {
      const ledger = ledgersByParticipantId[participant.id];
      let participantTotalCents = 0;

      for (const bill of ledger?.bills ?? []) {
        for (const line of bill.lines) {
          participantTotalCents += line.amount_cents;
          grandTotalCents += line.amount_cents;

          rows.push(
            [
              participant.display_name,
              bill.bill_description,
              line.item_description,
              formatUsdFromCents(line.amount_cents),
            ]
              .map(escapeCsvField)
              .join(",")
          );
        }
      }

      rows.push(
        [participant.display_name, "", "__PARTICIPANT_TOTAL__", formatUsdFromCents(participantTotalCents)]
          .map(escapeCsvField)
          .join(",")
      );
    }

    rows.push(["", "", "__GRAND_TOTAL__", formatUsdFromCents(grandTotalCents)].map(escapeCsvField).join(","));

    const csvContent = `${rows.join("\n")}\n`;
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8" });
    const timestamp = new Date().toISOString().slice(0, 19).replaceAll(":", "-");
    const fileName = `running-balances-${timestamp}.csv`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app">
      <div className="row">
        <h1 className="h1">Running balances</h1>
        <button className="btn btnPrimary" type="button" onClick={handleExportCsv} disabled={isLoading || Boolean(error)}>
          Export CSV
        </button>
      </div>

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
