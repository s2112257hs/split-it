import { useEffect, useState } from "react";
import ItemsTable, { type Item } from "./components/ItemsTable";
import Participants, { type Participant } from "./components/Participants";
import Assignments from "./components/Assignments";
import Totals from "./components/Totals";


type OcrResponse = {
  items: Item[];
  currency: string;
};

type ApiError = {
  error: { code: string; message: string };
};

type Step = "upload" | "verify" | "participants" | "assign" | "totals";

export default function App() {
  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

  const [step, setStep] = useState<Step>("upload");

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [currency, setCurrency] = useState<string>("USD");
  const [items, setItems] = useState<Item[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [assignments, setAssignments] = useState<Record<string, string[]>>({});

  const canParse = !!file && !isUploading;

  function onPickFile(f: File | null) {
    setFile(f);
    setError(null);
    setItems([]);
    setCurrency("USD");
    setStep("upload");
    // Participants are tied to a specific receipt/session; reset on new upload selection.
    setParticipants([]);

    // Revoke old preview URL before replacing it
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  }

  // Ensure we always revoke the current preview URL on unmount / change.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  async function onParseReceipt() {
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      const form = new FormData();
      form.append("image", file); // backend expects "image"

      const res = await fetch(`${API_BASE}/api/ocr`, {
        method: "POST",
        body: form,
      });

      const contentType = res.headers.get("content-type") || "";

      if (!res.ok) {
        if (contentType.includes("application/json")) {
          const errJson = (await res.json()) as ApiError;
          throw new Error(
            errJson?.error?.message || `Request failed (${res.status})`
          );
        }
        const text = await res.text();
        throw new Error(text || `Request failed (${res.status})`);
      }

      const data = (await res.json()) as OcrResponse;

      if (!data || !Array.isArray(data.items)) {
        throw new Error("Unexpected response from /api/ocr (missing 'items').");
      }

      setCurrency(data.currency || "USD");
      setItems(data.items);
      setStep("verify");
    } catch (e: any) {
      setError(e?.message ?? "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="app">
      <h1 className="h1">Split-It</h1>

      {step === "upload" && (
        <div className="card stack">
          <div className="subtle">Step 1 — Upload a receipt image</div>

          <input
            className="file"
            type="file"
            accept="image/*"
            onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
          />

          {previewUrl && (
            <div className="stack">
              <div className="small">Preview</div>
              <img className="preview" src={previewUrl} alt="Receipt preview" />
            </div>
          )}

          <button
            onClick={onParseReceipt}
            disabled={!canParse}
            className="btn btnPrimary"
          >
            {isUploading ? "Uploading & parsing…" : "Parse receipt"}
          </button>

          {error && (
            <div className="alert">
              <strong className="alertTitle">Error</strong>
              <div>{error}</div>
            </div>
          )}
        </div>
      )}

      {step === "verify" && (
        <ItemsTable
          currency={currency}
          items={items}
          onChange={setItems}
          onBack={() => setStep("upload")}
          onNext={() => setStep("participants")}
        />
      )}

      {step === "participants" && (
        <Participants
          participants={participants}
          onChange={setParticipants}
          onBack={() => setStep("verify")}
          onNext={() => setStep("assign")}
        />
      )}

      {step === "assign" && (
        <Assignments
          currency={currency}
          items={items}
          participants={participants}
          assignments={assignments}
          onChange={setAssignments}
          onBack={() => setStep("participants")}
          onNext={() => setStep("totals")}
        />
      )}

      {step === "totals" && (
        <Totals
          currency={currency}
          items={items}
          participants={participants}
          assignments={assignments}
          onBack={() => setStep("assign")}
          onReset={() => {
            setStep("upload");
            setFile(null);
            setError(null);
            setItems([]);
            setCurrency("USD");
            setParticipants([]);
            setAssignments({});
          }}
        />
      )}
    </div>
  );
}
