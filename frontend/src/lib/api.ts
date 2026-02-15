import type {
  ApiError,
  AssignmentsMap,
  CalculateSplitResponse,
  CreateReceiptResponse,
  Item,
  Participant,
} from "../types/split";

async function parseApiError(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    const errJson = (await response.json()) as ApiError;
    return errJson?.error?.message || `Request failed (${response.status})`;
  }

  const text = await response.text();
  return text || `Request failed (${response.status})`;
}

export async function createReceipt(file: File, description: string, apiBase: string): Promise<CreateReceiptResponse> {
  const form = new FormData();
  form.append("image", file);
  form.append("description", description);

  const response = await fetch(`${apiBase}/api/receipts`, {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const data = (await response.json()) as CreateReceiptResponse;

  if (!data || !Array.isArray(data.items) || typeof data.receipt_image_id !== "string") {
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

  const response = await fetch(`${apiBase}/api/receipts/${receiptImageId}/items`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ items }),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const data = (await response.json()) as { items?: Item[] };
  if (!data || !Array.isArray(data.items)) {
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

  const response = await fetch(`${apiBase}/api/receipts/${receiptImageId}/split`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ participants: participants.map((p) => p.id), assignments }),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const data = (await response.json()) as CalculateSplitResponse;

  if (!data || typeof data.grand_total_cents !== "number" || !data.totals_by_participant_id) {
    throw new Error("Unexpected response from /api/receipts/{receipt_image_id}/split.");
  }

  return data;
}

export async function listParticipants(apiBase: string): Promise<Participant[]> {
  const response = await fetch(`${apiBase}/api/participants`);
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const data = (await response.json()) as { participants?: Participant[] };
  if (!data || !Array.isArray(data.participants)) {
    throw new Error("Unexpected response from /api/participants.");
  }

  return data.participants;
}

export async function createParticipant(args: { display_name: string; apiBase: string }): Promise<Participant> {
  const response = await fetch(`${args.apiBase}/api/participants`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ display_name: args.display_name }),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as Participant;
}
