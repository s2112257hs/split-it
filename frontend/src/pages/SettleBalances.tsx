import { useEffect, useMemo, useState } from "react";
import {
  createParticipantRepayment,
  createParticipantSettlement,
  listParticipantFolios,
} from "../lib/api";
import { centsToUsdString, usdSignedStringToCents } from "../lib/money";
import type { FolioStatus, ParticipantFolioSummary } from "../types/split";

type Props = {
  apiBase: string;
  onBackHome: () => void;
};

function statusFromNetBalance(netBalanceCents: number): FolioStatus {
  if (netBalanceCents > 0) return "owes_you";
  if (netBalanceCents < 0) return "you_owe_them";
  return "settled";
}

function balanceSummaryText(folio: ParticipantFolioSummary): string {
  if (folio.net_balance_cents > 0) {
    return `${folio.display_name} owes you ${centsToUsdString(folio.net_balance_cents)}`;
  }
  if (folio.net_balance_cents < 0) {
    return `You owe ${folio.display_name} ${centsToUsdString(Math.abs(folio.net_balance_cents))}`;
  }
  return "Settled";
}

function centsToSignedUsdInput(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const remainder = String(abs % 100).padStart(2, "0");
  return `${sign}${dollars}.${remainder}`;
}

export default function SettleBalances({ apiBase, onBackHome }: Props) {
  const [folios, setFolios] = useState<ParticipantFolioSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [activeFolio, setActiveFolio] = useState<ParticipantFolioSummary | null>(null);
  const [amountInput, setAmountInput] = useState("");
  const [noteInput, setNoteInput] = useState("");
  const [modalError, setModalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const sortedFolios = useMemo(
    () => [...folios].sort((a, b) => a.display_name.localeCompare(b.display_name)),
    [folios]
  );

  const loadFolios = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listParticipantFolios(apiBase);
      setFolios(response);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch participant folios.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadFolios();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  const signedAmountCents = useMemo(() => {
    if (!amountInput.trim()) return null;
    try {
      return usdSignedStringToCents(amountInput);
    } catch {
      return null;
    }
  }, [amountInput]);

  const projectedNetBalanceCents =
    activeFolio && signedAmountCents !== null
      ? activeFolio.net_balance_cents - signedAmountCents
      : null;

  const openSettleModal = (folio: ParticipantFolioSummary) => {
    setActiveFolio(folio);
    setAmountInput("");
    setNoteInput("");
    setModalError(null);
    setSuccessMessage(null);
  };

  const closeSettleModal = () => {
    if (isSubmitting) return;
    setActiveFolio(null);
    setAmountInput("");
    setNoteInput("");
    setModalError(null);
  };

  const submitSettlement = async () => {
    if (!activeFolio) return;

    let cents: number;
    try {
      cents = usdSignedStringToCents(amountInput);
    } catch (e: unknown) {
      setModalError(e instanceof Error ? e.message : "Enter a valid amount.");
      return;
    }

    if (cents === 0) {
      setModalError("Amount cannot be zero.");
      return;
    }

    const trimmedNote = noteInput.trim();
    if (!trimmedNote) {
      setModalError("Description is required.");
      return;
    }

    const idempotencyKey = typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `folio-${Date.now()}-${Math.random().toString(36).slice(2)}`;

    setIsSubmitting(true);
    setModalError(null);

    try {
      if (cents > 0) {
        await createParticipantSettlement({
          participantId: activeFolio.participant_id,
          amount_cents: cents,
          note: trimmedNote,
          idempotency_key: idempotencyKey,
          apiBase,
        });
      } else {
        await createParticipantRepayment({
          participantId: activeFolio.participant_id,
          amount_cents: Math.abs(cents),
          note: trimmedNote,
          idempotency_key: idempotencyKey,
          apiBase,
        });
      }

      const actionLabel = cents > 0 ? "Settlement recorded" : "Repayment recorded";
      setSuccessMessage(`${actionLabel} for ${activeFolio.display_name}.`);
      setActiveFolio(null);
      setAmountInput("");
      setNoteInput("");
      setModalError(null);
      await loadFolios();
    } catch (e: unknown) {
      setModalError(e instanceof Error ? e.message : "Failed to save transaction.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="app">
      <h1 className="h1">Settle balances</h1>

      <div className="card tableCard stack">
        {isLoading && <div className="helper">Loading participants…</div>}

        {error && (
          <div className="alert">
            <strong>Couldn’t fetch balances.</strong>
            <div>{error}</div>
          </div>
        )}

        {successMessage && (
          <div className="alert alertSuccess">
            <strong>{successMessage}</strong>
          </div>
        )}

        {!isLoading && !error && (
          <div className="stack">
          <div className="actionsFooter">
          <button className="btn" onClick={onBackHome}>Back to home</button>
          </div>
            {sortedFolios.map((folio) => (
              <div key={folio.participant_id} className="participantsPanel">
                <div className="participantRow" style={{ borderTop: "none" }}>
                  <div className="row">
                    <div>
                      <strong>{folio.display_name}</strong>
                      <div className="helper">{balanceSummaryText(folio)}</div>
                    </div>
                    <div className="row">
                      <span className={folio.status === "settled" ? "statusOk" : "statusBad"}>{folio.status}</span>
                      <button className="btn btnPrimary" type="button" onClick={() => openSettleModal(folio)}>
                        Settle amount
                      </button>
                    </div>
                  </div>
                  <div className="helper">
                    Charged {centsToUsdString(folio.total_charged_cents)} • Paid {centsToUsdString(folio.total_settled_cents)} • Repaid {centsToUsdString(folio.total_repaid_cents)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}


      </div>

      {activeFolio && (
        <div className="modalBackdrop" role="presentation" onClick={closeSettleModal}>
          <div className="card modalCard stack" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <h2 className="stepTitle">Settle amount</h2>
            <div className="helper">{activeFolio.display_name}</div>
            <div className="helper">
              Positive amount = payment from participant. Negative amount = repayment to participant.
            </div>
            <div className="helper">Current: {balanceSummaryText(activeFolio)}</div>

            <label className="stack">
              <span>Amount (e.g. `25.00` or `-25.00`)</span>
              <input
                className="input"
                value={amountInput}
                onChange={(e) => setAmountInput(e.target.value)}
                placeholder="0.00"
                inputMode="decimal"
              />
            </label>

            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button
                className="btn"
                type="button"
                onClick={() => setAmountInput(centsToSignedUsdInput(activeFolio.net_balance_cents))}
                disabled={activeFolio.net_balance_cents === 0 || isSubmitting}
              >
                Settle in full
              </button>
            </div>

            <label className="stack">
              <span>Description</span>
              <input
                className="input"
                value={noteInput}
                onChange={(e) => setNoteInput(e.target.value)}
                placeholder="Cash, bank transfer, refund, etc."
              />
            </label>

            {projectedNetBalanceCents !== null && (
              <div className="helper">
                Projected status: <strong>{statusFromNetBalance(projectedNetBalanceCents)}</strong> • New balance {centsToUsdString(projectedNetBalanceCents)}
              </div>
            )}

            {modalError && <div className="alert">{modalError}</div>}

            <div className="actionsFooter">
              <button className="btn" type="button" onClick={closeSettleModal} disabled={isSubmitting}>Cancel</button>
              <button className="btn btnPrimary" type="button" onClick={() => void submitSettlement()} disabled={isSubmitting}>
                {isSubmitting ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
