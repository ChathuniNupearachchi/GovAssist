"""Verification-only test for the free PDF extraction chain
(langgraph-orchestration-branch, "PDF extraction -> free three-stage
chain"), run against `instructions_english_td.pdf` — the one scanned PDF
already in the corpus (6.5MB, 2 pages, 129 embedded images, 0
extractable characters).

This deliberately calls `extract_pdf_text_via_free_chain` directly on
the document's saved snapshot, NOT `extract_pdf_text` — the latter
checks `.extraction.json` first and would just return the existing
Claude-produced cache untouched, which is correct for production but
useless for comparing the free chain against it. Nothing here writes to
that cache; the existing extraction (Claude, 8,867 characters, method
"claude-api") stays exactly as it is regardless of what this test finds.

Section (a) — "Instructions to fill the application K-I.E.35A" — is
checked for explicitly: it's the source of the intake's 21 form-filling
instructions and exists nowhere else in the corpus, so its presence or
absence in the free chain's output is the one fact that actually matters
here, not just a raw character count.
"""

from __future__ import annotations

import pytest

from app.db.session import SessionLocal
from app.ingestion.pdf_extraction import extract_pdf_text_via_free_chain
from app.models import SourceDocument
from app.scraper.fetch import resolve_snapshot_path

TARGET_URL = "https://www.immigration.gov.lk/content/files/applications/instructions_english_td.pdf"

# The existing Claude-produced cache for this document, recorded here as
# a fixed comparison point — not re-read from the cache file, so this
# test can't accidentally start comparing against itself if the cache is
# ever regenerated.
EXISTING_CLAUDE_CHAR_COUNT = 8867
SECTION_A_MARKERS = ("Instructions to fill the application", "K - I.E. 35 A", "K-I.E.35A", "K-I.E. 35 A")


@pytest.mark.real_api
def test_free_chain_against_the_scanned_passport_instructions_pdf():
    db = SessionLocal()
    try:
        document = (
            db.query(SourceDocument).filter(SourceDocument.source_url == TARGET_URL).one()
        )
    finally:
        db.close()

    snapshot_file = resolve_snapshot_path(document.snapshot_path)
    text, method, model = extract_pdf_text_via_free_chain(snapshot_file)

    section_a_present = any(marker in text for marker in SECTION_A_MARKERS)

    print(
        f"\nfree chain method: {method} (model: {model})\n"
        f"free chain char count: {len(text)} (existing Claude extraction: {EXISTING_CLAUDE_CHAR_COUNT})\n"
        f"section (a) present: {section_a_present}"
    )

    # The one fact this verification actually gates on: section (a) — the
    # source of the intake's 21 form-filling instructions, found nowhere
    # else in the corpus — must survive whichever free stage produced the
    # text, or the free chain is not a safe default for documents like
    # this one and that must be visible as a failure, not just a number
    # in a printed line.
    assert section_a_present, (
        f"Section (a) did not survive the free chain (method={method}, "
        f"{len(text)} chars) — see the printed output above for what it "
        "actually produced."
    )
