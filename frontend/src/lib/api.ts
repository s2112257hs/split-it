import type {
  AssignmentsMap,
  CalculateSplitResponse,
  CreateReceiptResponse,
  Item,
  Participant,
} from "../types/split";
import { requestJson } from "./http";

export async function createReceipt(file: File, description: string, apiBase: string): Promise<CreateReceiptResponse> {
  const form = new FormData();
  form.append("image", file);
  form.append("description", description);

  const data = await requestJson<CreateReceiptResponse>(`${apiBase}/api/receipts`, {
    method: "POST",
    body: form,
  });

  if (!Array.isArray(data.items) || typeof data.receipt_image_id !== "string") {
    throw new Error("Unexpected response from /api/receipts.");
  }

  return data;
}

export async function replaceReceiptItems(args: {
  receiptImageId: string;
  items: Array<{ id?: string | null; description: string; price_cents: number }>;
  apiBase: string;
}): Promise<Item[]> {
  const { receiptImageId, items, apiBase } = args;

  const data = await requestJson<{ items?: Item[] }>(`${apiBase}/api/receipts/${receiptImageId}/items`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ items }),
  });

  if (!Array.isArray(data.items)) {
    throw new Error("Unexpected response from /api/receipts/{receipt_image_id}/items.");
  }

  return data.items;
}

export async function calculateSplit(args: {
  receiptImageId: string;
  participants: Participant[];
  assignments: AssignmentsMap;
  apiBase: string;
}): Promise<CalculateSplitResponse> {
  const { receiptImageId, participants, assignments, apiBase } = args;

  const data = await requestJson<CalculateSplitResponse>(`${apiBase}/api/receipts/${receiptImageId}/split`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ participants: participants.map((p) => p.id), assignments }),
  });

  if (typeof data.grand_total_cents !== "number" || !data.totals_by_participant_id) {
    throw new Error("Unexpected response from /api/receipts/{receipt_image_id}/split.");
  }

  return data;
}

export async function listParticipants(apiBase: string): Promise<Participant[]> {
  const data = await requestJson<{ participants?: Participant[] }>(`${apiBase}/api/participants`);
  if (!Array.isArray(data.participants)) {
    throw new Error("Unexpected response from /api/participants.");
  }

  return data.participants;
}

export async function createParticipant(args: { display_name: string; apiBase: string }): Promise<Participant> {
  return requestJson<Participant>(`${args.apiBase}/api/participants`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ display_name: args.display_name }),
  });
}
