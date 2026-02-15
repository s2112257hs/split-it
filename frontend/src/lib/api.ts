import type {
  ApiError,
  AssignmentsMap,
  CalculateSplitResponse,
  Item,
  OcrResponse,
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

export async function parseReceiptImage(file: File, description: string, apiBase: string): Promise<OcrResponse> {
  const form = new FormData();
  form.append("image", file);
  form.append("description", description);

  const response = await fetch(`${apiBase}/api/ocr`, {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const data = (await response.json()) as OcrResponse;

  if (!data || !Array.isArray(data.items)) {
    throw new Error("Unexpected response from /api/ocr (missing 'items').");
  }

  return data;
}

export async function calculateSplit(args: {
  participants: Participant[];
  items: Item[];
  assignments: AssignmentsMap;
  apiBase: string;
}): Promise<CalculateSplitResponse> {
  const { participants, items, assignments, apiBase } = args;

  const response = await fetch(`${apiBase}/api/calculate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ participants, items, assignments }),
  });

  const contentType = response.headers.get("content-type") || "";

  if (!response.ok) {
    if (contentType.includes("application/json")) {
      const errJson = (await response.json()) as ApiError;
      throw new Error(errJson?.error?.message || `Request failed (${response.status})`);
    }

    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }

  const data = (await response.json()) as CalculateSplitResponse;

  if (!data || typeof data.grand_total_cents !== "number" || !data.totals_by_participant_id) {
    throw new Error("Unexpected response from /api/calculate.");
  }

  return data;
}

export async function createParticipants(args: {
  participants: string[];
  apiBase: string;
}): Promise<Participant[]> {
  const { participants, apiBase } = args;

  const response = await fetch(`${apiBase}/api/participants`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ participants }),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const data = (await response.json()) as { participants?: Participant[] };
  if (!data || !Array.isArray(data.participants)) {
    throw new Error("Unexpected response from /api/participants.");
  }

  return data.participants;
}
