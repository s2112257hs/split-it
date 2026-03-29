import { Fragment, useEffect, useMemo, useState } from "react";

import { getBillSplitDetail } from "../lib/api";
import { centsToUsdString } from "../lib/money";
import type { BillSplitDetail } from "../types/split";

type Props = {
  apiBase: string;
  receiptImageId: string;
  onBackHome: () => void;
  onBackToBills: () => void;
};

const shortDateFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "2-digit",
  year: "2-digit",
});

function formatShortDate(isoDate: string): string {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) {
    return "--/--/--";
  }
  return shortDateFormatter.format(date);
}

function normalizeApiUrl(apiBase: string, apiPath: string): string {
  if (apiPath.startsWith("http://") || apiPath.startsWith("https://")) {
    return apiPath;
  }
  return `${apiBase}${apiPath}`;
}

export default function BillSplitDetailPage({ apiBase, receiptImageId, onBackHome, onBackToBills }: Props) {
  const [details, setDetails] = useState<BillSplitDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isBillModalOpen, setIsBillModalOpen] = useState(false);

  useEffect(() => {
    let isActive = true;

    const fetchDetails = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await getBillSplitDetail({ receiptImageId, apiBase });
        if (!isActive) {
          return;
        }
        setDetails(response);
      } catch (e: unknown) {
        if (!isActive) {
          return;
        }
        setError(e instanceof Error ? e.message : "Failed to fetch bill split details.");
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void fetchDetails();

    return () => {
      isActive = false;
    };
  }, [apiBase, receiptImageId]);

  const billImageUrl = useMemo(() => {
    if (!details) {
      return "";
    }
    return normalizeApiUrl(apiBase, details.show_bill_image_url);
  }, [apiBase, details]);

  return (
    <div className="app">
      <h1 className="h1">Bill split details</h1>

      <div className="card tableCard stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <button className="btn" onClick={onBackToBills}>Back to view bills</button>
          <div className="row">
            <button
              className="btn"
              type="button"
              onClick={() => setIsBillModalOpen(true)}
              disabled={!details?.has_image}
            >
              Show bill
            </button>
            <button className="btn" onClick={onBackHome}>Back to home</button>
          </div>
        </div>

        {isLoading && <div className="helper">Loading bill details…</div>}

        {error && (
          <div className="alert">
            <strong>Couldn’t fetch bill details.</strong>
            <div>{error}</div>
          </div>
        )}

        {!isLoading && !error && details && (
          <>
            <div className="helper">
              {details.bill_description} • {formatShortDate(details.entered_at)}
            </div>

            {details.participants.length === 0 ? (
              <div className="helper">No split allocations found for this bill yet.</div>
            ) : (
              <table className="table" style={{ minWidth: 0 }}>
                <tbody>
                  {details.participants.map((participant) => (
                    <Fragment key={participant.participant_id}>
                      <tr>
                        <td colSpan={4}><strong>{participant.participant_name}</strong></td>
                      </tr>
                      {participant.lines.map((line) => (
                        <tr key={line.receipt_item_id}>
                          <td>{line.item_description}</td>
                          <td style={{ textAlign: "right" }}>{centsToUsdString(line.amount_cents)}</td>
                          <td />
                          <td />
                        </tr>
                      ))}
                      <tr>
                        <td><strong>Total</strong></td>
                        <td />
                        <td style={{ textAlign: "right" }}><strong>{centsToUsdString(participant.participant_total_cents)}</strong></td>
                        <td />
                      </tr>
                    </Fragment>
                  ))}
                  <tr>
                    <td><strong>Bill total</strong></td>
                    <td />
                    <td />
                    <td style={{ textAlign: "right" }}><strong>{centsToUsdString(details.bill_total_cents)}</strong></td>
                  </tr>
                </tbody>
              </table>
            )}
          </>
        )}
      </div>

      {isBillModalOpen && details?.has_image && (
        <div
          className="modalBackdrop"
          role="presentation"
          onClick={() => setIsBillModalOpen(false)}
        >
          <div
            className="card modalCard stack"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong>{details.bill_description}</strong>
              <button className="btn" type="button" onClick={() => setIsBillModalOpen(false)}>
                Close
              </button>
            </div>
            <div className="previewFrame" style={{ maxHeight: "70vh" }}>
              <img src={billImageUrl} alt={details.bill_description} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
