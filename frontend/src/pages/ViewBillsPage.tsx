import { useEffect, useMemo, useState } from "react";

import { listBillPreviews } from "../lib/api";
import type { BillPreview } from "../types/split";

type Props = {
  apiBase: string;
  onBackHome: () => void;
  onOpenBill: (receiptImageId: string) => void;
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

function isWithinDateRange(bill: BillPreview, dateFrom: string, dateTo: string): boolean {
  if (!dateFrom && !dateTo) {
    return true;
  }

  const enteredAt = new Date(bill.entered_at);
  if (Number.isNaN(enteredAt.getTime())) {
    return false;
  }

  if (dateFrom) {
    const from = new Date(`${dateFrom}T00:00:00`);
    if (enteredAt < from) {
      return false;
    }
  }

  if (dateTo) {
    const to = new Date(`${dateTo}T23:59:59.999`);
    if (enteredAt > to) {
      return false;
    }
  }

  return true;
}

export default function ViewBillsPage({ apiBase, onBackHome, onOpenBill }: Props) {
  const [bills, setBills] = useState<BillPreview[]>([]);
  const [descriptionQuery, setDescriptionQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const fetchBills = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const previews = await listBillPreviews(apiBase);
        if (!isActive) {
          return;
        }
        setBills(previews);
      } catch (e: unknown) {
        if (!isActive) {
          return;
        }
        setError(e instanceof Error ? e.message : "Failed to fetch bills.");
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void fetchBills();

    return () => {
      isActive = false;
    };
  }, [apiBase]);

  const filteredBills = useMemo(() => {
    const query = descriptionQuery.trim().toLowerCase();

    return bills.filter((bill) => {
      const descriptionMatches =
        !query || bill.bill_description.toLowerCase().includes(query);

      return descriptionMatches && isWithinDateRange(bill, dateFrom, dateTo);
    });
  }, [bills, descriptionQuery, dateFrom, dateTo]);

  return (
    <div className="app">
      <h1 className="h1">View bills</h1>

      <div className="card tableCard stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <button className="btn" onClick={onBackHome}>Back to home</button>
          {!isLoading && !error && (
            <div className="helper">
              {filteredBills.length} bill{filteredBills.length === 1 ? "" : "s"}
            </div>
          )}
        </div>

        <div className="filtersRow">
          <label className="stack">
            <span className="helper">Search by description</span>
            <input
              className="input"
              value={descriptionQuery}
              onChange={(e) => setDescriptionQuery(e.target.value)}
              placeholder="e.g. Uber, groceries, dinner"
            />
          </label>

          <label className="stack">
            <span className="helper">Date from</span>
            <input
              className="input"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </label>

          <label className="stack">
            <span className="helper">Date to</span>
            <input
              className="input"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </label>
        </div>

        <div className="helper">Click a bill card to open split details.</div>

        {isLoading && <div className="helper">Loading bills…</div>}

        {error && (
          <div className="alert">
            <strong>Couldn’t fetch bills.</strong>
            <div>{error}</div>
          </div>
        )}

        {!isLoading && !error && filteredBills.length === 0 && (
          <div className="helper">No bills found for your current search and date filter.</div>
        )}

        {!isLoading && !error && filteredBills.length > 0 && (
          <div className="billGrid">
            {filteredBills.map((bill) => (
              <button
                key={bill.receipt_image_id}
                type="button"
                className="billCard"
                onClick={() => onOpenBill(bill.receipt_image_id)}
                aria-label={`Open ${bill.bill_description}`}
              >
                <div className="billCardImageWrap">
                  {bill.has_image ? (
                    <img
                      className="billCardImage"
                      src={normalizeApiUrl(apiBase, bill.preview_image_url)}
                      alt={bill.bill_description}
                      loading="lazy"
                    />
                  ) : (
                    <div className="billCardImagePlaceholder">No image</div>
                  )}
                </div>

                <div className="billCardBody">
                  <div className="billCardDescription">{bill.bill_description}</div>
                  <div className="billCardDate">{formatShortDate(bill.entered_at)}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
