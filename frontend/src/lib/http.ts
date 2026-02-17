import type { ApiError } from "../types/split";

async function parseApiError(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    const errJson = (await response.json()) as ApiError;
    return errJson?.error?.message || `Request failed (${response.status})`;
  }

  const text = await response.text();
  return text || `Request failed (${response.status})`;
}

export async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as T;
}
