import { useState } from "react";
import Assignments from "../components/Assignments";
import ItemsTable from "../components/ItemsTable";
import Participants from "../components/Participants";
import Totals from "../components/Totals";
import { useReceiptUpload } from "../hooks/useReceiptUpload";
import { parseReceiptImage } from "../lib/api";
import type { AssignmentsMap, Item, Participant, Step } from "../types/split";

export default function SplitFlow() {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

  const [step, setStep] = useState<Step>("upload");
  const [currency, setCurrency] = useState<string>("USD");
  const [items, setItems] = useState<Item[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [assignments, setAssignments] = useState<AssignmentsMap>({});

  const {
    file,
    previewUrl,
    isUploading,
    error,
    canParse,
    pickFile,
    beginUpload,
    endUpload,
    setError,
    resetUploadState,
  } = useReceiptUpload();

  function handlePickFile(nextFile: File | null) {
    pickFile(nextFile);
    setItems([]);
    setCurrency("USD");
    setStep("upload");
    setParticipants([]);
    setAssignments({});
  }

  async function handleParseReceipt() {
    if (!file) return;

    beginUpload();

    try {
      const data = await parseReceiptImage(file, apiBase);
      setCurrency(data.currency || "USD");
      setItems(data.items);
      setStep("verify");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      endUpload();
    }
  }

  function resetFlow() {
    setStep("upload");
    setCurrency("USD");
    setItems([]);
    setParticipants([]);
    setAssignments({});
    resetUploadState();
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
            onChange={(e) => handlePickFile(e.target.files?.[0] ?? null)}
          />

          {previewUrl && (
            <div className="stack">
              <div className="small">Preview</div>
              <img className="preview" src={previewUrl} alt="Receipt preview" />
            </div>
          )}

          <button
            onClick={handleParseReceipt}
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
          onReset={resetFlow}
        />
      )}
    </div>
  );
}
