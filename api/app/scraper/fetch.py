"""Shared rate-limited fetch + snapshot persistence.

Used by both the HTML scraper and PDF extraction (ingestion) — same
politeness rules and the same snapshot-before-parsing discipline for
every request this pipeline makes to the source site. See the
phase-3-ingestion-pipeline change's design.md for the rationale behind
each decision here.
"""

import hashlib
import time
from pathlib import Path

import httpx

# Identifies this pipeline to the source site, per design.md's decision.
# The contact address is a placeholder — replace with a real, monitored
# address before this runs against production traffic.
USER_AGENT = (
    "GovAssist-Ingestion/1.0 "
    "(+https://github.com/govassist/govassist; "
    "automated ingestion for a citizen document-checklist app; "
    "contact: govassist-dev@example.com)"
)

# Fixed delay between requests — appropriate at this phase's volume (8
# requests total). See design.md: a token-bucket limiter is unwarranted
# complexity at this scale.
RATE_LIMIT_SECONDS = 2.0

# Snapshots live under api/data/snapshots/, named by content hash.
# SourceDocument.snapshot_path stores the path relative to API_ROOT.
API_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = API_ROOT / "data" / "snapshots"

_last_request_at: float | None = None


def _throttle() -> None:
    """Block until RATE_LIMIT_SECONDS have passed since the last request
    made through this module."""
    global _last_request_at
    if _last_request_at is not None:
        elapsed = time.monotonic() - _last_request_at
        remaining = RATE_LIMIT_SECONDS - elapsed
        if remaining > 0:
            time.sleep(remaining)
    _last_request_at = time.monotonic()


def fetch_and_snapshot(url: str, extension: str) -> tuple[str, str]:
    """Fetch a URL, hash its raw content, and save it to disk before any
    parsing touches it.

    `extension` is the snapshot file's extension (".html" or ".pdf"),
    supplied by the caller rather than guessed from the URL.

    Returns (content_hash, snapshot_path) where snapshot_path is relative
    to API_ROOT. Raises httpx.HTTPStatusError on a non-2xx response.
    """
    _throttle()
    response = httpx.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
        follow_redirects=True,
    )
    response.raise_for_status()

    raw_bytes = response.content
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    absolute_path = SNAPSHOT_DIR / f"{content_hash}{extension}"
    if not absolute_path.exists():
        # Content-addressed: identical content re-fetched under any URL
        # writes the same bytes to the same path — a harmless no-op.
        absolute_path.write_bytes(raw_bytes)

    relative_path = str(absolute_path.relative_to(API_ROOT)).replace("\\", "/")
    return content_hash, relative_path


def resolve_snapshot_path(snapshot_path: str) -> Path:
    """Resolve a SourceDocument.snapshot_path (relative to API_ROOT) to an
    absolute filesystem path."""
    return API_ROOT / snapshot_path
