import { useMemo, useState } from "react";
import Assignments from "../components/Assignments";
import ItemsTable from "../components/ItemsTable";
import Participants from "../components/Participants";
import Totals from "../components/Totals";
import UploadReceipt from "../components/UploadReceipt";
import { useReceiptUpload } from "../hooks/useReceiptUpload";
import { calculateSplit, createParticipant, createReceipt, listParticipants, replaceReceiptItems } from "../lib/api";
import type { AssignmentsMap, Item, Participant, Step } from "../types/split";
import { isLocalParticipantId, makeLocalParticipantId } from "../utils/participantIds";

const stepOrder: Step[] = ["upload", "verify", "participants", "assign", "totals"];
type Props = {
  onBackHome: () => void;
};

export default function SplitFlow({ onBackHome }: Props) {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";
  const [step, setStep] = useState<Step>("upload");
  const [currency, setCurrency] = useState<string>("USD");
  const [items, setItems] = useState<Item[]>([]);
  const [allParticipants, setAllParticipants] = useState<Participant[]>([]);
  const [selectedParticipantIds, setSelectedParticipantIds] = useState<string[]>([]);
  const [assignments, setAssignments] = useState<AssignmentsMap>({});
  const [billDescription, setBillDescription] = useState("");
  const [receiptImageId, setReceiptImageId] = useState<string | null>(null);

  const selectedParticipants = useMemo(
    () => allParticipants.filter((participant) => selectedParticipantIds.includes(participant.id)),
    [allParticipants, selectedParticipantIds]
  );

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
    setAllParticipants([]);
    setSelectedParticipantIds([]);
    setAssignments({});
    setReceiptImageId(null);
  }

  async function handleParseReceipt() {
    if (!file) return;
    beginUpload();

    try {
      const data = await createReceipt(file, billDescription.trim(), apiBase);
      setCurrency(data.currency || "USD");
      setItems(data.items.map((item) => ({ id: item.temp_id, description: item.description, price_cents: item.price_cents })));
      setReceiptImageId(data.receipt_image_id);
      setStep("verify");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      endUpload();
    }
  }

  async function handlePersistItems() {
    if (!receiptImageId) return;

    try {
      const persisted = await replaceReceiptItems({
        receiptImageId,
        items: items.map((item) => ({ id: null, description: item.description, price_cents: item.price_cents })),
        apiBase,
      });
      setItems(persisted);
      const existing = await listParticipants(apiBase);
      setAllParticipants(existing);
      setSelectedParticipantIds([]);
      setStep("participants");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save items.");
    }
  }

  function handleAddParticipant(displayName: string) {
    const participant: Participant = {
      id: makeLocalParticipantId(),
      display_name: displayName,
      running_total_cents: 0,
    };

    setAllParticipants((prev) => [...prev, participant]);
    setSelectedParticipantIds((prev) => [...prev, participant.id]);
  }

  async function handlePersistParticipants() {
    try {
      const selected = allParticipants.filter((participant) => selectedParticipantIds.includes(participant.id));

      const persistedSelected = await Promise.all(
        selected.map(async (participant) => {
          if (!isLocalParticipantId(participant.id)) {
            return participant;
          }
          return createParticipant({ display_name: participant.display_name, apiBase });
        })
      );

      const refreshedAll = await listParticipants(apiBase);
      setAllParticipants(refreshedAll);

      const selectedByName = new Set(persistedSelected.map((participant) => participant.display_name.trim().toLowerCase()));
      setSelectedParticipantIds(
        refreshedAll
          .filter((participant) => selectedByName.has(participant.display_name.trim().toLowerCase()))
          .map((participant) => participant.id)
      );

      setStep("assign");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save participants.");
    }
  }

  async function handlePersistAssignments() {
    if (!receiptImageId) return;

    try {
      await calculateSplit({ receiptImageId, participants: selectedParticipants, assignments, apiBase });
      setStep("totals");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save assignments.");
    }
  }

  function resetFlow() {
    setStep("upload");
    setCurrency("USD");
    setItems([]);
    setAllParticipants([]);
    setSelectedParticipantIds([]);
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
        <UploadReceipt
          billDescription={billDescription}
          isUploading={isUploading}
          previewUrl={previewUrl}
          file={file}
          canParse={canParse}
          error={error}
          onBillDescriptionChange={setBillDescription}
          onPickFile={handlePickFile}
          onParseReceipt={handleParseReceipt}
          onBackHome={onBackHome}
        />
      )}

      {step === "verify" && (
        <ItemsTable
          currency={currency}
          items={items}
          onChange={setItems}
          onBack={() => setStep("upload")}
          onNext={handlePersistItems}
        />
      )}

      {step === "participants" && (
        <Participants
          participants={allParticipants}
          selectedParticipantIds={selectedParticipantIds}
          onSelectionChange={setSelectedParticipantIds}
          onAddParticipant={handleAddParticipant}
          onBack={() => setStep("verify")}
          onNext={handlePersistParticipants}
        />
      )}

      {step === "assign" && (
        <Assignments
          currency={currency}
          items={items}
          participants={selectedParticipants}
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
          participants={selectedParticipants}
          assignments={assignments}
          onBack={() => setStep("assign")}
          onReset={resetFlow}
        />
      )}
    </div>
  );
}
