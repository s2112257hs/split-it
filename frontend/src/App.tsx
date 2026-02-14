import { useMemo, useState } from "react";
import ItemsTable, { type Item } from "./components/ItemsTable";

type OcrResponse = {
  items: Item[];
  currency: string;
};

type ApiError = {
  error: { code: string; message: string };
};

type Step = "upload" | "verify";

export default function App() {
  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

  const [step, setStep] = useState<Step>("upload");

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [currency, setCurrency] = useState<string>("USD");
  const [items, setItems] = useState<Item[]>([]);

  const canParse = !!file && !isUploading;

  function onPickFile(f: File | null) {
    setFile(f);
    setError(null);
    setItems([]);
    setCurrency("USD");
    setStep("upload");

    // Manage preview URL lifecycle safely
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  }

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
          throw new Error(errJson?.error?.message || `Request failed (${res.status})`);
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
    <div
      style={{
        maxWidth: 900,
        margin: "40px auto",
        padding: "0 16px",
        fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Arial",
        color: "#111",
      }}
    >
      <h1 style={{ marginBottom: 8 }}>Split-It</h1>

      {step === "upload" && (
        <div style={{ display: "grid", gap: 12, padding: 16, border: "1px solid #ddd", borderRadius: 12 }}>
          <div style={{ opacity: 0.8 }}>Step 1 — Upload a receipt image</div>

          <input
            type="file"
            accept="image/*"
            onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
          />

          {previewUrl && (
            <div style={{ display: "grid", gap: 8 }}>
              <div style={{ fontSize: 14, opacity: 0.8 }}>Preview</div>
              <img
                src={previewUrl}
                alt="Receipt preview"
                style={{ maxWidth: "100%", borderRadius: 12, border: "1px solid #eee" }}
              />
            </div>
          )}

          <button
            onClick={onParseReceipt}
            disabled={!canParse}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #111",
              background: canParse ? "#111" : "#eee",
              color: canParse ? "#fff" : "#666",
              cursor: canParse ? "pointer" : "not-allowed",
              width: "fit-content",
            }}
          >
            {isUploading ? "Uploading & parsing…" : "Parse receipt"}
          </button>

          {error && (
            <div style={{ padding: 12, borderRadius: 10, background: "#fff3f3", border: "1px solid #ffd0d0" }}>
              <strong style={{ display: "block", marginBottom: 4 }}>Error</strong>
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
          // Next will become Step 3 (participants)
          onNext={() => alert("Step 3 next (participants)")}
        />
      )}
    </div>
  );
}
