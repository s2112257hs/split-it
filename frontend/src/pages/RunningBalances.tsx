import { useEffect, useMemo, useState } from "react";
import { listParticipants } from "../lib/api";
import { centsToUsdString } from "../lib/money";
import type { Participant } from "../types/split";

type Props = {
  apiBase: string;
  onBackHome: () => void;
};

export default function RunningBalances({ apiBase, onBackHome }: Props) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const fetchParticipants = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const data = await listParticipants(apiBase);
        if (!isActive) return;
        setParticipants(data);
      } catch (e: unknown) {
        if (!isActive) return;
        setError(e instanceof Error ? e.message : "Failed to fetch running balances.");
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void fetchParticipants();

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
          <div className="tableWrap">
            <table className="table" style={{ minWidth: 0 }}>
              <thead>
                <tr>
                  <th>Participant</th>
                  <th style={{ textAlign: "right" }}>Running balance (USD)</th>
                </tr>
              </thead>
              <tbody>
                {sortedParticipants.map((participant) => (
                  <tr key={participant.id}>
                    <td>{participant.display_name}</td>
                    <td style={{ textAlign: "right" }}>{centsToUsdString(participant.running_total_cents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="actionsFooter">
          <button className="btn" onClick={onBackHome}>Back to home</button>
        </div>
      </div>
    </div>
  );
}
