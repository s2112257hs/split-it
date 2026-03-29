ALTER TABLE receipt_images
ADD COLUMN IF NOT EXISTS status TEXT;

ALTER TABLE receipt_images
ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMPTZ;

UPDATE receipt_images
SET
    status = 'draft',
    finalized_at = NULL
WHERE status IS NULL OR status <> 'finalized';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'receipt_images_status_check'
    ) THEN
        ALTER TABLE receipt_images
        DROP CONSTRAINT receipt_images_status_check;
    END IF;
END;
$$;

ALTER TABLE receipt_images
ADD CONSTRAINT receipt_images_status_check
CHECK (status IN ('draft', 'finalized'));

ALTER TABLE receipt_images
ALTER COLUMN status SET DEFAULT 'draft';

ALTER TABLE receipt_images
ALTER COLUMN status SET NOT NULL;

WITH per_item AS (
    SELECT
        ri.id AS receipt_id,
        ritem.id AS receipt_item_id,
        ritem.item_price_cents::bigint AS item_price_cents,
        COALESCE(SUM(pia.amount_cents), 0)::bigint AS allocated_cents,
        MAX(pia.created_at) AS max_alloc_created_at
    FROM receipt_images ri
    JOIN receipt_items ritem ON ritem.receipt_image_id = ri.id
    LEFT JOIN participant_item_allocations pia ON pia.receipt_item_id = ritem.id
    GROUP BY ri.id, ritem.id, ritem.item_price_cents
),
per_receipt AS (
    SELECT
        receipt_id,
        COUNT(*) AS item_count,
        COUNT(*) FILTER (WHERE allocated_cents = item_price_cents) AS matched_item_count,
        MAX(max_alloc_created_at) AS max_alloc_created_at
    FROM per_item
    GROUP BY receipt_id
)
UPDATE receipt_images ri
SET
    status = 'finalized',
    finalized_at = COALESCE(pr.max_alloc_created_at, ri.created_at, NOW())
FROM per_receipt pr
WHERE ri.id = pr.receipt_id
  AND pr.item_count > 0
  AND pr.matched_item_count = pr.item_count;

CREATE INDEX IF NOT EXISTS idx_receipt_images_status_created_at
ON receipt_images (status, created_at DESC);
