CREATE TABLE IF NOT EXISTS participant_settlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id UUID NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    paid_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note TEXT
);
