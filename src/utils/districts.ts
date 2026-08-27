/**
 * Mirrors `api/app/chat/deterministic.py`'s `DISTRICTS` list exactly —
 * the canonical spelling `GET /studios` validates against. Needed
 * because the resolve response never exposes the citizen's answered
 * district directly (see design.md's addendum on this); the app
 * tracks it client-side from the chat turn where the pending question
 * was `answer_type: "district"`, then canonicalizes whatever the
 * citizen typed against this same list before calling `getStudios`.
 */
export const DISTRICTS = [
  "Colombo",
  "Gampaha",
  "Kalutara",
  "Kandy",
  "Matale",
  "Nuwara Eliya",
  "Galle",
  "Matara",
  "Hambantota",
  "Jaffna",
  "Kilinochchi",
  "Mannar",
  "Vavuniya",
  "Mullaitivu",
  "Batticaloa",
  "Ampara",
  "Trincomalee",
  "Kurunegala",
  "Puttalam",
  "Anuradhapura",
  "Polonnaruwa",
  "Badulla",
  "Monaragala",
  "Ratnapura",
  "Kegalle",
] as const;

const DISTRICT_BY_LOWER: Record<string, string> = Object.fromEntries(
  DISTRICTS.map((d) => [d.toLowerCase(), d])
);

/** Case-insensitive canonicalization, same lookup shape as the backend's own `_DISTRICT_BY_LOWER`. Returns null for anything that isn't an exact (case-insensitive) match to one of the 25 districts. */
export function canonicalizeDistrict(raw: string): string | null {
  return DISTRICT_BY_LOWER[raw.trim().toLowerCase()] ?? null;
}
