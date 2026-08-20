"""Shared structured-extraction types — Phase 6.6.

`ExtractedBlock` is the common intermediate representation both HTML and
PDF extraction produce: an ordered sequence of prose paragraphs, lists,
and tables, each tagged with the section heading nearest its position in
the source. The chunker (chunking.py) turns this into chunks; a table or
list block is never split.

`document_title` has no column on `SourceDocument` to read from, so it's
resolved from a small, explicit per-document map — the same "match by
URL substring" convention `app.seed.phase5_approve_documents` already
uses for this exact 8-document corpus, rather than parsing an HTML
`<title>` tag (present but not equally reliable — `studio_e.php`'s
`<title>` is just the department's name, not a page-specific title) or
guessing from a PDF filename.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import SourceDocument

CONTENT_TYPES = ("prose", "table", "list")


@dataclass(frozen=True)
class ExtractedBlock:
    content_type: str  # "prose" | "table" | "list"
    text: str
    section_heading: str | None


# URL substring -> friendly document title, covering the same 8 approved
# documents `app.seed.phase5_approve_documents` names.
_DOCUMENT_TITLES: list[tuple[str, str]] = [
    ("pages_e.php?id=7", "General Information on Passports"),
    ("pages_e.php?id=8", "Issue of Passports"),
    ("pages_e.php?id=9", "Overseas Applications"),
    ("pages_e.php?id=10", "Amendments"),
    ("studio_e.php", "Authorised Photo Studios"),
    ("instructions_english_td.pdf", "Instructions for Completing the Passport Application"),
    ("passport_application.pdf", "Passport Application Form (K 35 A)"),
    ("amendment.pdf", "Amendment Application Form"),
]


def document_title(source_document: SourceDocument) -> str:
    """Resolve a document's citizen-facing title from its source URL."""
    for substring, title in _DOCUMENT_TITLES:
        if substring in source_document.source_url:
            return title
    # Fallback for any document outside the known 8 — better than a
    # crash, and still non-null per the metadata requirement.
    return source_document.source_url.rsplit("/", 1)[-1] or source_document.source_url
