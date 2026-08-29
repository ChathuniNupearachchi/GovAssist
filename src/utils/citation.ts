import type { Citation } from "../api/types";

/**
 * `Citation` (see `api/app/api/schemas.py`'s `CitationOut`) carries no
 * document title — only `source_document_id`, `source_url`,
 * `verified_at`. `SourceCitation` just renders a formatted string, so
 * this builds one from what's actually available: the source's domain
 * (readable, not a raw UUID) plus a human date, matching the
 * "<Publisher> · Verified <date>" shape the existing screens already
 * use with hardcoded copy.
 */
export function formatCitation(citation: Citation): string {
  let host = citation.source_url;
  try {
    host = new URL(citation.source_url).hostname.replace(/^www\./, "");
  } catch {
    // Malformed URL (shouldn't happen for a verified source) — fall back to the raw string.
  }

  if (!citation.verified_at) {
    return host;
  }

  const date = new Date(citation.verified_at);
  const formatted = Number.isNaN(date.getTime())
    ? citation.verified_at
    : date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

  return `${host} · Verified ${formatted}`;
}
