"""admin-dashboard change, task 7.1 — reads a source document's actual
extraction method from the ingestion pipeline's per-content-hash cache
file, per design.md's "Extraction method is read from the ingestion
cache, not a new column" decision.

Read-only against the filesystem (never writes), and entirely
independent of `app.ingestion.pdf_extraction` (which lives in the
citizen system and is never imported here) — this module only knows
the cache file's location and shape, both of which are stable, small
surface area to duplicate rather than import across the package
boundary this change deliberately keeps separate.
"""

from __future__ import annotations

import json
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[3] / "api"
_SNAPSHOT_DIR = _API_ROOT / "data" / "snapshots"


def extraction_method(content_hash: str, document_type: str) -> str | None:
    """Returns the extraction method actually used for a PDF (e.g.
    "pdfplumber", "tesseract", "gemini-flash-vision", "claude-api"), or
    "unknown" when the document is a PDF but its cache entry is missing
    or unreadable. Returns None for a non-PDF document — extraction only
    applies to PDFs, so an HTML source shows no extraction method at
    all, distinct from a PDF whose cache entry can't be found."""
    if document_type != "pdf":
        return None

    cache_path = _SNAPSHOT_DIR / f"{content_hash}.extraction.json"
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        method = data.get("method")
        return method if isinstance(method, str) and method else "unknown"
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "unknown"
