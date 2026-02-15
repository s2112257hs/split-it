export type Item = {
  id: string;
  description: string;
  price_cents: number;
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
  allocations: Array<{
    participant_id: string;
    receipt_item_id: string;
    amount_cents: number;
  }>;
};
