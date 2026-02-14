import { useMemo, useState } from "react";
import type { Participant } from "../types/split";

type Props = {
  participants: Participant[];
  onChange: (next: Participant[]) => void;
  onBack?: () => void;
  onNext?: () => void;
};

function makeId() {
  return `p_${crypto.randomUUID()}`;
}

export default function Participants({ participants, onChange, onBack, onNext }: Props) {
  const [newName, setNewName] = useState("");
  const [showErrors, setShowErrors] = useState(false);

  const normalizedNames = useMemo(() => {
    return participants.map((p) => p.name.trim().toLowerCase());
  }, [participants]);

  const errors = useMemo(() => {
    const e: Record<string, string> = {};

    participants.forEach((p, idx) => {
      const name = p.name.trim();
      if (!name) e[p.id] = "Name is required.";
      const norm = name.toLowerCase();
      const firstIndex = normalizedNames.indexOf(norm);
      if (name && firstIndex !== -1 && firstIndex !== idx) {
        e[p.id] = "Duplicate name.";
      }
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

  function updateName(id: string, name: string) {
    onChange(participants.map((p) => (p.id === id ? { ...p, name } : p)));
  }

  function remove(id: string) {
    onChange(participants.filter((p) => p.id !== id));
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div>
        <h2 style={{ margin: 0 }}>Step 3 — Participants</h2>
        <div style={{ opacity: 0.75, marginTop: 4 }}>
          Add everyone who will be splitting the bill.
        </div>
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        <input
          value={newName}
          placeholder="Enter name (e.g., Ibrahim)"
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") addParticipant();
          }}
          style={input}
        />
        <button onClick={addParticipant} style={btn} disabled={!newName.trim()}>
          + Add
        </button>
      </div>

      <div style={{ border: "1px solid #ddd", borderRadius: 12, overflow: "hidden" }}>
        <div style={{ padding: "10px 12px", background: "#f6f6f6", borderBottom: "1px solid #e8e8e8" }}>
          <strong>People</strong>
        </div>

        {participants.length === 0 ? (
          <div style={{ padding: 12, opacity: 0.8 }}>No participants yet.</div>
        ) : (
          <div style={{ display: "grid" }}>
            {participants.map((p) => {
              const err = errors[p.id];
              return (
                <div key={p.id} style={{ padding: 12, borderTop: "1px solid #eee" }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <input
                      value={p.name}
                      onChange={(e) => updateName(p.id, e.target.value)}
                      placeholder="Name"
                      style={{
                        ...input,
                        borderColor: showErrors && err ? "#b00020" : "#ccc",
                      }}
                    />
                    <button onClick={() => remove(p.id)} style={dangerBtn}>
                      Remove
                    </button>
                  </div>

                  {showErrors && err && (
                    <div style={{ marginTop: 6, color: "#b00020", fontSize: 12 }}>
                      {err}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 10, justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 10 }}>
          {onBack && (
            <button onClick={onBack} style={btn}>
              Back
            </button>
          )}
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          {onNext && (
            <button
              onClick={() => {
                if (!canNext) {
                  setShowErrors(true);
                  return;
                }
                onNext();
              }}
              style={primaryBtn}
            >
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const input: React.CSSProperties = {
  width: "100%",
  padding: "9px 10px",
  borderRadius: 10,
  border: "1px solid #ccc",
  outline: "none",
  fontSize: 14,
};

const btn: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #222",
  background: "#fff",
  cursor: "pointer",
};

const primaryBtn: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #111",
  background: "#111",
  color: "#fff",
  cursor: "pointer",
};

const dangerBtn: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #b00020",
  background: "#fff",
  color: "#b00020",
  cursor: "pointer",
};
