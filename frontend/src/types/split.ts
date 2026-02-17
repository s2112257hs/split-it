export type Item = {
  id: string;
  description: string;
  price_cents: number;
  quantity: number;
};

export type PreviewItem = {
  temp_id: string;
  description: string;
  price_cents: number;
};

export type Participant = {
  id: string;
  display_name: string;
  running_total_cents: number;
};

export type AssignmentsMap = Record<string, string[]>;

export type Step = "upload" | "verify" | "participants" | "assign" | "totals";

export type CreateReceiptResponse = {
  receipt_image_id: string;
  items: PreviewItem[];
  currency: string;
};

export type ApiError = {
  error?: { code?: string; message?: string };
};

export type CalculateSplitResponse = {
  receipt_image_id: string;
  totals_by_participant_id: Record<string, number>;
  grand_total_cents: number;
  receipt_items: Array<{
    id: string;
    description: string;
  }>;
  allocations: Array<{
    participant_id: string;
    receipt_item_id: string;
    amount_cents: number;
  }>;
};

export type ParticipantLedgerLine = {
  receipt_item_id: string;
  item_description: string;
  amount_cents: number;
};

export type ParticipantLedgerBill = {
  receipt_image_id: string;
  bill_description: string;
  lines: ParticipantLedgerLine[];
};

export type ParticipantLedger = {
  participant_id: string;
  computed_total_cents: number;
  bills: ParticipantLedgerBill[];
};
