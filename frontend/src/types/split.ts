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

export type FolioStatus = "owes_you" | "settled" | "you_owe_them";

export type ParticipantFolioSummary = {
  participant_id: string;
  display_name: string;
  total_charged_cents: number;
  total_settled_cents: number;
  total_repaid_cents: number;
  net_balance_cents: number;
  status: FolioStatus;
  overpayment_cents: number;
};

export type ParticipantFoliosResponse = {
  folios: ParticipantFolioSummary[];
};

export type FolioSettlementResponse = {
  transaction_type: "settlement";
  settlement_id: string;
  previous_net_balance_cents: number;
  payment_amount_cents: number;
  settlement_amount_cents: number;
  new_net_balance_cents: number;
  status: FolioStatus;
  overpayment_cents: number;
  overpayment_happened: boolean;
  idempotency_replayed: boolean;
};

export type FolioRepaymentResponse = {
  transaction_type: "repayment";
  repayment_id: string;
  previous_net_balance_cents: number;
  repayment_amount_cents: number;
  new_net_balance_cents: number;
  status: FolioStatus;
  overpayment_cents: number;
  idempotency_replayed: boolean;
};

export type RunningBalanceLine = {
  receipt_item_id: string;
  item_name: string;
  contribution_cents: number;
};

export type RunningBalanceBill = {
  receipt_id: string;
  bill_description: string;
  bill_total_cents: number;
  lines: RunningBalanceLine[];
};

export type RunningBalanceTransactionEvent = {
  event_id: string;
  event_at: string;
  amount_cents: number;
  reference_details: string;
};

export type RunningBalanceParticipant = {
  participant_id: string;
  participant_name: string;
  participant_total_cents: number;
  total_charged_cents: number;
  total_settled_cents: number;
  total_repaid_cents: number;
  net_balance_cents: number;
  status: FolioStatus;
  bills: RunningBalanceBill[];
  settlement_events: RunningBalanceTransactionEvent[];
  repayment_events: RunningBalanceTransactionEvent[];
};

export type RunningBalancesResponse = {
  participants: RunningBalanceParticipant[];
};

export type BillPreview = {
  receipt_image_id: string;
  bill_description: string;
  entered_at: string;
  has_image: boolean;
  preview_image_url: string;
};

export type BillPreviewsResponse = {
  bills: BillPreview[];
};

export type BillSplitDetailLine = {
  receipt_item_id: string;
  item_description: string;
  amount_cents: number;
};

export type BillSplitDetailParticipant = {
  participant_id: string;
  participant_name: string;
  participant_total_cents: number;
  lines: BillSplitDetailLine[];
};

export type BillSplitDetail = {
  receipt_image_id: string;
  bill_description: string;
  entered_at: string;
  bill_total_cents: number;
  has_image: boolean;
  show_bill_image_url: string;
  participants: BillSplitDetailParticipant[];
};
