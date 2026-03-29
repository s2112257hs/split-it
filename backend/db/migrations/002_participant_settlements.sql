ALTER TABLE participants
DROP CONSTRAINT IF EXISTS participants_running_total_cents_check;

CREATE TABLE IF NOT EXISTS participant_settlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id UUID NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    paid_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note TEXT,
    idempotency_key TEXT UNIQUE,
    created_by TEXT,
    reversed_at TIMESTAMPTZ,
    reversed_by TEXT,
    reversal_note TEXT,
    previous_net_balance_cents INTEGER NOT NULL,
    new_net_balance_cents INTEGER NOT NULL
);

CREATE OR REPLACE FUNCTION apply_settlement_delta_to_running_total()
RETURNS TRIGGER AS $$
DECLARE
    old_effect INTEGER := 0;
    new_effect INTEGER := 0;
BEGIN
    IF TG_OP <> 'INSERT' AND OLD.reversed_at IS NULL THEN
        old_effect := -OLD.amount_cents;
    END IF;

    IF TG_OP <> 'DELETE' AND NEW.reversed_at IS NULL THEN
        new_effect := -NEW.amount_cents;
    END IF;

    IF TG_OP = 'INSERT' THEN
        UPDATE participants
        SET running_total_cents = running_total_cents + new_effect
        WHERE id = NEW.participant_id;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.participant_id = OLD.participant_id THEN
            UPDATE participants
            SET running_total_cents = running_total_cents + (new_effect - old_effect)
            WHERE id = NEW.participant_id;
        ELSE
            UPDATE participants
            SET running_total_cents = running_total_cents - old_effect
            WHERE id = OLD.participant_id;

            UPDATE participants
            SET running_total_cents = running_total_cents + new_effect
            WHERE id = NEW.participant_id;
        END IF;
        RETURN NEW;
    ELSE
        UPDATE participants
        SET running_total_cents = running_total_cents - old_effect
        WHERE id = OLD.participant_id;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_apply_settlement_delta ON participant_settlements;
CREATE TRIGGER trg_apply_settlement_delta
AFTER INSERT OR UPDATE OR DELETE ON participant_settlements
FOR EACH ROW
EXECUTE FUNCTION apply_settlement_delta_to_running_total();
