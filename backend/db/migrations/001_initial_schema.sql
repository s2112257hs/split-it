CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS receipt_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    image_blob BYTEA,
    image_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT receipt_images_storage_check
        CHECK ((image_blob IS NOT NULL) <> (image_path IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS receipt_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_image_id UUID NOT NULL REFERENCES receipt_images(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    item_price_cents INTEGER NOT NULL CHECK (item_price_cents >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name TEXT NOT NULL UNIQUE,
    running_total_cents INTEGER NOT NULL DEFAULT 0 CHECK (running_total_cents >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS participant_item_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id UUID NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    receipt_item_id UUID NOT NULL REFERENCES receipt_items(id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (participant_id, receipt_item_id)
);

CREATE OR REPLACE FUNCTION validate_allocation_amount()
RETURNS TRIGGER AS $$
DECLARE
    max_cents INTEGER;
BEGIN
    SELECT item_price_cents INTO max_cents
    FROM receipt_items
    WHERE id = NEW.receipt_item_id;

    IF max_cents IS NULL THEN
        RAISE EXCEPTION 'Receipt item % not found', NEW.receipt_item_id;
    END IF;

    IF NEW.amount_cents > max_cents THEN
        RAISE EXCEPTION 'Allocation amount (%) cannot exceed item price (%)', NEW.amount_cents, max_cents;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_allocation_amount ON participant_item_allocations;
CREATE TRIGGER trg_validate_allocation_amount
BEFORE INSERT OR UPDATE ON participant_item_allocations
FOR EACH ROW
EXECUTE FUNCTION validate_allocation_amount();

CREATE OR REPLACE FUNCTION apply_allocation_delta_to_running_total()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE participants
        SET running_total_cents = running_total_cents + NEW.amount_cents
        WHERE id = NEW.participant_id;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.participant_id = OLD.participant_id THEN
            UPDATE participants
            SET running_total_cents = running_total_cents + NEW.amount_cents - OLD.amount_cents
            WHERE id = NEW.participant_id;
        ELSE
            UPDATE participants
            SET running_total_cents = running_total_cents - OLD.amount_cents
            WHERE id = OLD.participant_id;
            UPDATE participants
            SET running_total_cents = running_total_cents + NEW.amount_cents
            WHERE id = NEW.participant_id;
        END IF;
        RETURN NEW;
    ELSE
        UPDATE participants
        SET running_total_cents = running_total_cents - OLD.amount_cents
        WHERE id = OLD.participant_id;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_apply_allocation_delta ON participant_item_allocations;
CREATE TRIGGER trg_apply_allocation_delta
AFTER INSERT OR UPDATE OR DELETE ON participant_item_allocations
FOR EACH ROW
EXECUTE FUNCTION apply_allocation_delta_to_running_total();
