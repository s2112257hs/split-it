import { useMemo, useState } from "react";
import type { Participant } from "../types/split";

type Props = {
  participants: Participant[];
  selectedParticipantIds: string[];
  onSelectionChange: (nextSelectedIds: string[]) => void;
  onAddParticipant: (displayName: string) => void;
  onBack?: () => void;
  onNext?: () => Promise<void> | void;
};

function unique(values: string[]): string[] {
  return Array.from(new Set(values));
}

export default function Participants({
  participants,
  selectedParticipantIds,
  onSelectionChange,
  onAddParticipant,
  onBack,
  onNext,
}: Props) {
  const [newName, setNewName] = useState("");
  const [showError, setShowError] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const selectedSet = useMemo(() => new Set(selectedParticipantIds), [selectedParticipantIds]);

  const normalizedExistingNames = useMemo(
    () => new Set(participants.map((participant) => participant.display_name.trim().toLowerCase())),
    [participants]
  );

  const newNameError = useMemo(() => {
    const normalized = newName.trim().toLowerCase();
    if (!normalized) return "";
    if (normalizedExistingNames.has(normalized)) return "Participant already exists.";
    return "";
  }, [newName, normalizedExistingNames]);

  function toggleParticipant(participantId: string, checked: boolean) {
    if (checked) {
      onSelectionChange(unique([...selectedParticipantIds, participantId]));
      return;
    }
    onSelectionChange(selectedParticipantIds.filter((id) => id !== participantId));
  }

  function addParticipant() {
    const trimmed = newName.trim();
    if (!trimmed || newNameError) return;
    onAddParticipant(trimmed);
    setNewName("");
  }

  const canContinue = selectedParticipantIds.length > 0;

  return (
    <div className="card formCard stack">
      <div>
        <h2 className="stepTitle">Step 3 — Participants</h2>
        <div className="helper">Select who is part of this bill. Add new people if needed.</div>
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        <input
          className={`input ${newNameError ? "inputError" : ""}`}
          value={newName}
          placeholder="Add participant (e.g., Ibrahim)"
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") addParticipant();
          }}
          disabled={isSaving}
        />
        <button className="btn btnPrimary" onClick={addParticipant} disabled={!newName.trim() || Boolean(newNameError) || isSaving}>
          Add
        </button>
      </div>
      {newNameError && <div className="errorText">{newNameError}</div>}

      <div className="participantsPanel">
        <div style={{ background: "var(--panel-alt)", padding: 12 }}>
          <strong>All participants</strong>
        </div>

        {participants.length === 0 ? (
          <div className="participantRow">No participants yet.</div>
        ) : (
          participants.map((participant) => {
            const checked = selectedSet.has(participant.id);
            return (
              <label className="participantRow" key={participant.id} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => toggleParticipant(participant.id, e.target.checked)}
                  disabled={isSaving}
                />
                <span>{participant.display_name}</span>
              </label>
            );
          })
        )}
      </div>

      {showError && !canContinue && <div className="errorText">Select at least one participant.</div>}

      <div className="actionsFooter actionsFooterSticky">
        {onBack ? <button className="btn" onClick={onBack} disabled={isSaving}>Back</button> : <span />}
        {onNext && (
          <button
            className="btn btnPrimary"
            disabled={isSaving}
            onClick={async () => {
              if (!canContinue) {
                setShowError(true);
                return;
              }
              setIsSaving(true);
              try {
                await onNext();
              } finally {
                setIsSaving(false);
              }
            }}
          >
            {isSaving ? "Saving…" : "Next"}
          </button>
        )}
      </div>
    </div>
  );
}
