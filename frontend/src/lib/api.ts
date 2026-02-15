import type { ApiError, OcrResponse } from "../types/split";

export async function parseReceiptImage(file: File, description: string, apiBase: string): Promise<OcrResponse> {
  const form = new FormData();
  form.append("image", file);
  form.append("description", description);

  const response = await fetch(`${apiBase}/api/ocr`, {
    method: "POST",
    body: form,
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

  const data = (await response.json()) as OcrResponse;

  if (!data || !Array.isArray(data.items)) {
    throw new Error("Unexpected response from /api/ocr (missing 'items').");
  }

  return data;
}
