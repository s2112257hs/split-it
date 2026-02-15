import { useRef, useState } from "react";
import Assignments from "../components/Assignments";
import ItemsTable from "../components/ItemsTable";
import Participants from "../components/Participants";
import Totals from "../components/Totals";
import { useReceiptUpload } from "../hooks/useReceiptUpload";
import { calculateSplit, createParticipants, parseReceiptImage } from "../lib/api";
import type { AssignmentsMap, Item, Participant, Step } from "../types/split";

const stepOrder: Step[] = ["upload", "verify", "participants", "assign", "totals"];

export default function SplitFlow() {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";
  const fileRef = useRef<HTMLInputElement | null>(null);

  const [step, setStep] = useState<Step>("upload");
  const [currency, setCurrency] = useState<string>("USD");
  const [items, setItems] = useState<Item[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [assignments, setAssignments] = useState<AssignmentsMap>({});
  const [isDragging, setIsDragging] = useState(false);
  const [billDescription, setBillDescription] = useState("");
  const [receiptImageId, setReceiptImageId] = useState<string | null>(null);

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

  const stepIndex = stepOrder.indexOf(step);

  function handlePickFile(nextFile: File | null) {
    pickFile(nextFile);
    setItems([]);
    setCurrency("USD");
    setStep("upload");
    setParticipants([]);
    setAssignments({});
    setReceiptImageId(null);
  }

  async function handleParseReceipt() {
    if (!file) return;
    beginUpload();

    try {
      const data = await parseReceiptImage(file, billDescription.trim(), apiBase);
      setCurrency(data.currency || "USD");
      setItems(data.items);
      setReceiptImageId(data.receipt_image_id ?? null);
      setStep("verify");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      endUpload();
    }
  }

  async function handlePersistParticipants() {
    try {
      const saved = await createParticipants({
        participants: participants.map((participant) => participant.name),
        apiBase,
      });
      setParticipants(saved);
      setStep("assign");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save participants.");
    }
  }

  async function handlePersistAssignments() {
    try {
      await calculateSplit({ participants, items, assignments, apiBase });
      setStep("totals");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save assignments.");
    }
  }

  function resetFlow() {
    setStep("upload");
    setCurrency("USD");
    setItems([]);
    setParticipants([]);
    setAssignments({});
    setBillDescription("");
    setReceiptImageId(null);
    resetUploadState();
  }

  return (
    <div className="app">
      <h1 className="h1">Split-It</h1>
      {error && step !== "upload" && (
        <div className="alert" style={{ marginBottom: 12 }}>
          <strong>Request failed</strong>
          <div>{error}</div>
        </div>
      )}

      <div className="stepper">
        <p className="stepLabel">Step {stepIndex + 1} of 5</p>
        <div className="progress" aria-hidden>
          <div className="progressFill" style={{ width: `${((stepIndex + 1) / 5) * 100}%` }} />
        </div>
      </div>

      {step === "upload" && (
        <div className="card formCard stack">
          <div>
            <h2 className="stepTitle">Step 1 — Upload receipt</h2>
            <div className="helper">Upload → Add bill description → Preview → Parse</div>
          </div>


          <label className="stack" style={{ gap: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Bill description</span>
            <input
              className="input"
              value={billDescription}
              onChange={(e) => setBillDescription(e.target.value)}
              placeholder="Dinner at Joe's"
              disabled={isUploading}
            />
          </label>

          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg"
            style={{ display: "none" }}
            disabled={isUploading}
            onChange={(e) => handlePickFile(e.target.files?.[0] ?? null)}
          />

          <button
            className={`dropzone ${isDragging ? "dropzoneActive" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              handlePickFile(e.dataTransfer.files?.[0] ?? null);
            }}
            onClick={() => fileRef.current?.click()}
            disabled={isUploading}
          >
            <strong style={{ fontSize: 15 }}>Drop receipt image here</strong>
            <span className="helper">PNG or JPG • clear photo works best</span>
          </button>

          {previewUrl && (
            <div className="stack">
              <div className="previewFrame">
                <img src={previewUrl} alt="Receipt preview" />
              </div>
              <div>
                <div style={{ fontSize: 13 }}>{file?.name}</div>
                {file && <div className="helper">{(file.size / 1024).toFixed(1)} KB</div>}
              </div>
            </div>
          )}

          <button onClick={handleParseReceipt} disabled={!canParse || !billDescription.trim()} className="btn btnPrimary">
            {isUploading ? "Parsing…" : "Parse receipt"}
          </button>

          {error && (
            <div className="alert">
              <strong>Couldn’t parse the receipt</strong>
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
          onNext={handlePersistParticipants}
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
          onNext={handlePersistAssignments}
        />
      )}

      {step === "totals" && receiptImageId && (
        <Totals
          apiBase={apiBase}
          receiptImageId={receiptImageId}
          currency={currency}
          items={items}
          participants={participants}
          onBack={() => setStep("assign")}
          onReset={resetFlow}
        />
      )}
    </div>
  );
}
