export type Item = {
  id: string;
  description: string;
  price_cents: number;
};

export type Participant = {
  id: string;
  name: string;
};

export type AssignmentsMap = Record<string, string[]>;

export type Step = "upload" | "verify" | "participants" | "assign" | "totals";

export type OcrResponse = {
  items: Item[];
  currency: string;
  receipt_image_id?: string | null;
};

export type ApiError = {
  error?: { code?: string; message?: string };
};

export type CalculateSplitResponse = {
  totals_by_participant_id: Record<string, number>;
  grand_total_cents: number;
};
