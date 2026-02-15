import { useMemo, useState } from "react";
import type { Participant } from "../types/split";

type Props = {
  participants: Participant[];
  onChange: (next: Participant[]) => void;
  onBack?: () => void;
  onNext?: () => Promise<void> | void;
};

function makeId() {
  return `p_${crypto.randomUUID()}`;
}

export default function Participants({ participants, onChange, onBack, onNext }: Props) {
  const [newName, setNewName] = useState("");
  const [showErrors, setShowErrors] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const normalizedNames = useMemo(() => participants.map((p) => p.name.trim().toLowerCase()), [participants]);

  const errors = useMemo(() => {
    const e: Record<string, string> = {};
    participants.forEach((p, idx) => {
      const name = p.name.trim();
      if (!name) e[p.id] = "Name is required.";
      const firstIndex = normalizedNames.indexOf(name.toLowerCase());
      if (name && firstIndex !== -1 && firstIndex !== idx) e[p.id] = "Duplicate name.";
    });
    return e;
  }, [participants, normalizedNames]);

  const canNext = participants.length > 0 && Object.keys(errors).length === 0;

  function addParticipant() {
    const name = newName.trim();
    if (!name) return;
    onChange([...participants, { id: makeId(), name }]);
    setNewName("");
  }

  return (
    <div className="card formCard stack">
      <div>
        <h2 className="stepTitle">Step 3 — Participants</h2>
        <div className="helper">Quickly add names and avoid blanks/duplicates.</div>
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        <input
          className="input"
          value={newName}
          placeholder="Enter name (e.g., Ibrahim)"
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") addParticipant();
          }}
        />
        <button className="btn btnPrimary" onClick={addParticipant} disabled={!newName.trim() || isSaving}>Add</button>
      </div>

      <div className="participantsPanel">
        <div style={{ background: "var(--panel-alt)", padding: 12 }}>
          <strong>People</strong>
        </div>

        {participants.length === 0 ? (
          <div className="participantRow">No participants yet.</div>
        ) : (
          participants.map((p) => {
            const err = errors[p.id];
            return (
              <div className="participantRow" key={p.id}>
                <div style={{ display: "flex", gap: 10 }}>
                  <input
                    className={`input ${showErrors && err ? "inputError" : ""}`}
                    value={p.name}
                    onChange={(e) => onChange(participants.map((x) => (x.id === p.id ? { ...x, name: e.target.value } : x)))}
                    disabled={isSaving}
                  />
                  <button className="btn btnDanger" onClick={() => onChange(participants.filter((x) => x.id !== p.id))} disabled={isSaving}>
                    Remove
                  </button>
                </div>
                {showErrors && err && <div className="errorText">{err}</div>}
              </div>
            );
          })
        )}
      </div>

      <div className="actionsFooter actionsFooterSticky">
        {onBack ? <button className="btn" onClick={onBack} disabled={isSaving}>Back</button> : <span />}
        {onNext && (
          <button
            className="btn btnPrimary"
            disabled={isSaving}
            onClick={async () => {
              if (!canNext) {
                setShowErrors(true);
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
