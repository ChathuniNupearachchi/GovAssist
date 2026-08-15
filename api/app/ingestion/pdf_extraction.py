"""PDF fetch + text extraction.

Fetching reuses the scraper's rate-limited, User-Agent-identified,
snapshot-before-parsing fetch (see app.scraper.fetch). Text extraction
reads from the saved snapshot, never from the fetch response directly.

Extraction tries pdfplumber's text layer first. Scanned PDFs (confirmed
for instructions_english_td.pdf: 6.5MB, 2 pages, 129 embedded images, 0
extractable characters) have no text layer to read, so extraction falls
back to the Claude API, which reads scanned documents natively — the
fourth of CLAUDE.md's narrow Claude API jobs. See design.md's "Scanned
PDFs fall back to the Claude API" decision.
"""

import base64
import json
from datetime import datetime
from pathlib import Path

import anthropic
import pdfplumber
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.ingestion.config import TARGET_PDFS
from app.models import SourceDocument
from app.scraper.fetch import SNAPSHOT_DIR, fetch_and_snapshot, resolve_snapshot_path

load_dotenv()

# Below this many non-whitespace characters, pdfplumber's extraction is
# treated as "no usable text" (a scanned document), not just a short PDF.
MIN_USABLE_TEXT_CHARS = 50

CLAUDE_MODEL = "claude-opus-5"

_claude_client: anthropic.Anthropic | None = None


def fetch_pdf(db: Session, url: str) -> SourceDocument:
    """Fetch one PDF, snapshot it, and persist it as a pending SourceDocument."""
    content_hash, snapshot_path = fetch_and_snapshot(url, extension=".pdf")

    document = SourceDocument(
        source_url=url,
        snapshot_path=snapshot_path,
        content_hash=content_hash,
        document_type="pdf",
        fetched_at=datetime.utcnow(),
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def fetch_all_target_pdfs(db: Session) -> list[SourceDocument]:
    """Fetch every configured target PDF."""
    return [fetch_pdf(db, url) for url in TARGET_PDFS]


def _extract_pdf_text_via_pdfplumber(snapshot_file: Path) -> str:
    """Extract text from a PDF's text layer, concatenated across pages."""
    pages_text = []
    with pdfplumber.open(snapshot_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n\n".join(pages_text)


def _get_claude_client() -> anthropic.Anthropic:
    global _claude_client
    if _claude_client is None:
        _claude_client = anthropic.Anthropic()
    return _claude_client


def _extract_pdf_text_via_claude(snapshot_file: Path) -> str:
    """Extract text from a scanned PDF via the Claude API (OCR-by-LLM).

    Sent as a base64 document content block per the Messages API's PDF
    support (no beta header required).
    """
    pdf_bytes = snapshot_file.read_bytes()
    encoded = base64.standard_b64encode(pdf_bytes).decode("ascii")

    client = _get_claude_client()
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8192,
        output_config={"effort": "low"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": encoded,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Transcribe every word of visible text in this "
                            "document, verbatim and in reading order. Do not "
                            "summarize, paraphrase, or omit any section. "
                            "Output only the transcribed text, no commentary."
                        ),
                    },
                ],
            }
        ],
    )

    text_parts = [block.text for block in response.content if block.type == "text"]
    return "\n\n".join(text_parts)


def _extraction_cache_path(content_hash: str) -> Path:
    return SNAPSHOT_DIR / f"{content_hash}.extraction.json"


def _read_extraction_cache(content_hash: str) -> dict | None:
    cache_path = _extraction_cache_path(content_hash)
    if not cache_path.exists():
        return None
    return json.loads(cache_path.read_text(encoding="utf-8"))


def _write_extraction_cache(content_hash: str, method: str, text: str, model: str | None = None) -> None:
    cache_path = _extraction_cache_path(content_hash)
    payload = {
        "method": method,
        "text": text,
        "model": model,
        "extracted_at": datetime.utcnow().isoformat(),
    }
    cache_path.write_text(json.dumps(payload), encoding="utf-8")


def extract_pdf_text(source_document: SourceDocument) -> str:
    """Extract text from a PDF SourceDocument's saved snapshot.

    Tries pdfplumber's text layer first. Falls back to the Claude API when
    that yields no usable text (a scanned document). The method and result
    are cached per content hash — see _extraction_cache_path — so a given
    document is never sent to the paid Claude API more than once, and
    which method produced a document's text is recorded, not assumed.
    """
    cached = _read_extraction_cache(source_document.content_hash)
    if cached is not None:
        return cached["text"]

    snapshot_file = resolve_snapshot_path(source_document.snapshot_path)
    text = _extract_pdf_text_via_pdfplumber(snapshot_file)

    if len(text.strip()) >= MIN_USABLE_TEXT_CHARS:
        _write_extraction_cache(source_document.content_hash, method="pdfplumber", text=text)
        return text

    text = _extract_pdf_text_via_claude(snapshot_file)
    _write_extraction_cache(
        source_document.content_hash, method="claude-api", text=text, model=CLAUDE_MODEL
    )
    return text
