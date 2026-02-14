// src/lib/money.ts

export function centsToUsdString(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const rem = abs % 100;
  return `${sign}${dollars}.${String(rem).padStart(2, "0")}`;
}

/**
 * Parse a user-entered USD string to cents.
 * Accepts: "12", "12.", "12.3", "12.30", "$12.30", " 12.30 "
 * Rejects: empty, multiple dots, more than 2 decimals, non-numeric.
 */
export function usdStringToCents(input: string): number {
  const s = input.trim().replace(/^\$/, "");
  if (!s) throw new Error("Price is required.");

  // Allow 0-2 decimal digits so "12." is considered valid while typing.
  if (!/^\d+(\.\d{0,2})?$/.test(s)) {
    throw new Error("Enter a valid price like 12, 12.3, or 12.34");
  }

  const [whole, frac = ""] = s.split(".");
  const dollars = Number(whole);

  // frac can be "" (for "12.") or "3" or "34"
  const centsPart = Number((frac + "00").slice(0, 2));

  return dollars * 100 + centsPart;
}
