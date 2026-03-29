DROP TRIGGER IF EXISTS trg_apply_repayment_delta ON participant_repayments;
DROP FUNCTION IF EXISTS apply_repayment_delta_to_running_total();

DROP TABLE IF EXISTS participant_repayments;
