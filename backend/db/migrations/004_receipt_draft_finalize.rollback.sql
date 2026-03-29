DROP INDEX IF EXISTS idx_receipt_images_status_created_at;

ALTER TABLE receipt_images
DROP CONSTRAINT IF EXISTS receipt_images_status_check;

ALTER TABLE receipt_images
DROP COLUMN IF EXISTS finalized_at;

ALTER TABLE receipt_images
DROP COLUMN IF EXISTS status;
