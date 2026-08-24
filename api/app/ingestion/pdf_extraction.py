"""PDF fetch + text extraction.

Fetching reuses the scraper's rate-limited, User-Agent-identified,
snapshot-before-parsing fetch (see app.scraper.fetch). Text extraction
reads from the saved snapshot, never from the fetch response directly.

Extraction tries pdfplumber's text layer first. Scanned PDFs (confirmed
for instructions_english_td.pdf: 6.5MB, 2 pages, 129 embedded images, 0
extractable characters) have no text layer to read, so extraction falls
back to a three-stage free chain before ever touching a paid API —
langgraph-orchestration-branch's cost-engineering decision ("free tiers
wherever the output is not citizen-facing"; a scraped source document's
extracted text is never shown to a citizen directly, only distilled into
rule data a human reviewer approves):

  1. pdfplumber — unchanged, above.
  2. Tesseract via `pytesseract` — free, local, unlimited, no API. Each
     page is rasterized with PyMuPDF and OCR'd; the result is checked for
     plausible quality (character count and garbled-run detection, see
     `_tesseract_quality_ok`) rather than assumed good just because it
     ran — a scanned government form is exactly the case where a
     confident-looking but wrong transcription is worse than none.
  3. Gemini Flash vision (`app.llm.gateway`'s free-tier default) — only
     when Tesseract's output fails that quality check.

Only if all three fail does extraction fall back to the Claude API,
which reads scanned documents natively — the fourth of CLAUDE.md's
narrow Claude API jobs, now a last resort behind `PDF_OCR_CLAUDE_LAST_
RESORT_ENABLED` rather than the first fallback. See design.md's "PDF
extraction → free three-stage chain" decision.

DOES NOT touch the three PDFs already cached in `.extraction.json` —
`extract_pdf_text` checks the cache before attempting any extraction
method at all (see below), so this chain only ever runs for a document
that has never been successfully extracted before.
"""

import base64
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path

import anthropic
import litellm
import pdfplumber
import pymupdf
import pytesseract
from dotenv import load_dotenv
from PIL import Image
from sqlalchemy.orm import Session

from app.ingestion.blocks import ExtractedBlock
from app.ingestion.config import TARGET_PDFS
from app.llm.gateway import model_for
from app.models import SourceDocument
from app.scraper.fetch import SNAPSHOT_DIR, fetch_and_snapshot, resolve_snapshot_path

load_dotenv()

# Below this many non-whitespace characters, pdfplumber's extraction is
# treated as "no usable text" (a scanned document), not just a short PDF.
MIN_USABLE_TEXT_CHARS = 50

CLAUDE_MODEL = "claude-opus-5"

# Each stage of the free chain, independently toggleable — "every
# provider swap keeps its existing fallback path" means each of these
# can be turned off (rate-limited, misbehaving, or just for comparison)
# without code changes and without losing the stages after it.
PDF_OCR_TESSERACT_ENABLED = os.environ.get("PDF_OCR_TESSERACT_ENABLED", "true").strip().lower() != "false"
PDF_OCR_GEMINI_ENABLED = os.environ.get("PDF_OCR_GEMINI_ENABLED", "true").strip().lower() != "false"
# The paid last resort — on by default (a citizen-facing checklist should
# never silently lose a source document because both free stages had a
# bad day), but explicitly named as a last resort and flaggable off for
# a run where spending anything at all is unacceptable.
PDF_OCR_CLAUDE_LAST_RESORT_ENABLED = (
    os.environ.get("PDF_OCR_CLAUDE_LAST_RESORT_ENABLED", "true").strip().lower() != "false"
)

_claude_client: anthropic.Anthropic | None = None


def _configure_tesseract() -> None:
    """Points `pytesseract` at the Tesseract binary. `TESSERACT_CMD`
    overrides explicitly; otherwise this only intervenes on the Windows
    dev machine where the UB-Mannheim installer's default location isn't
    on PATH — Docker/Linux deployment installs `tesseract-ocr` via apt,
    where it's on PATH already, so this is a no-op there."""
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        return
    windows_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if os.name == "nt" and windows_default.exists():
        pytesseract.pytesseract.tesseract_cmd = str(windows_default)


# Garbled OCR output tends to be either mostly symbols (misread scan
# noise) or one giant "word" per line (missed word-boundary detection) —
# neither of which a real transcription looks like. Neither check is
# proof of quality, but together they catch the failure modes actually
# seen from Tesseract on a noisy scan, which is the point: detect poor
# output rather than assume a successful run produced a good one.
_GARBLED_RUN_PATTERN = re.compile(r"[^\w\s]{8,}")
_MAX_OVERLONG_WORD_FRACTION = 0.05
_MIN_ALNUM_FRACTION = 0.5


def _tesseract_quality_ok(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < MIN_USABLE_TEXT_CHARS:
        return False
    if _GARBLED_RUN_PATTERN.search(stripped):
        return False
    words = stripped.split()
    if not words:
        return False
    overlong = sum(1 for w in words if len(w) > 30)
    if overlong / len(words) > _MAX_OVERLONG_WORD_FRACTION:
        return False
    alnum = sum(1 for c in stripped if c.isalnum())
    if alnum / len(stripped) < _MIN_ALNUM_FRACTION:
        return False
    return True


def _pdf_pages_to_png_bytes(snapshot_file: Path, dpi: int = 200) -> list[bytes]:
    """Rasterizes every page of a PDF to PNG bytes via PyMuPDF — the
    input both Tesseract and Gemini vision need; pdfplumber and the
    Claude path (which sends the PDF document natively) never call this."""
    images = []
    doc = pymupdf.open(snapshot_file)
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            images.append(pix.tobytes("png"))
    finally:
        doc.close()
    return images


def _extract_pdf_text_via_tesseract(snapshot_file: Path) -> str:
    _configure_tesseract()
    pages_text = []
    for png_bytes in _pdf_pages_to_png_bytes(snapshot_file):
        image = Image.open(io.BytesIO(png_bytes))
        pages_text.append(pytesseract.image_to_string(image))
    return "\n\n".join(pages_text)


_OCR_INSTRUCTION = (
    "Transcribe every word of visible text on this document page, verbatim "
    "and in reading order. Do not summarize, paraphrase, or omit any "
    "section. Output only the transcribed text, no commentary."
)


def _extract_pdf_text_via_gemini(snapshot_file: Path) -> str:
    """OCR-by-LLM on Gemini's free tier — `app.llm.gateway`'s job/model
    convention (`LLM_MODEL_PDF_VISION` to override), called directly via
    `litellm.completion` rather than `structured_completion` since this
    wants free-form transcribed text, not a Pydantic schema."""
    model = model_for("pdf_vision")
    pages_text = []
    for png_bytes in _pdf_pages_to_png_bytes(snapshot_file):
        encoded = base64.standard_b64encode(png_bytes).decode("ascii")
        response = litellm.completion(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _OCR_INSTRUCTION},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                    ],
                }
            ],
        )
        pages_text.append(response.choices[0].message.content or "")
    return "\n\n".join(pages_text)


def extract_pdf_text_via_free_chain(snapshot_file: Path) -> tuple[str, str, str | None]:
    """Runs the free chain (Tesseract, then Gemini vision) and returns
    `(text, method, model)`. Raises if every enabled free stage failed or
    produced unusable output — callers decide whether to fall back to the
    paid Claude last resort or propagate the failure.

    Public (not prefixed `_`) because the verification test for this
    chain (`tests/ingestion/test_pdf_extraction_chain.py`) calls it
    directly against `instructions_english_td.pdf`'s snapshot, deliberately
    bypassing `extract_pdf_text`'s cache so that verification run never
    touches — let alone overwrites — the already-cached, already-working
    extraction for that document.
    """
    if PDF_OCR_TESSERACT_ENABLED:
        try:
            tesseract_text = _extract_pdf_text_via_tesseract(snapshot_file)
        except Exception:
            tesseract_text = ""
        if _tesseract_quality_ok(tesseract_text):
            return tesseract_text, "tesseract", None

    if PDF_OCR_GEMINI_ENABLED:
        try:
            gemini_text = _extract_pdf_text_via_gemini(snapshot_file)
        except Exception:
            gemini_text = ""
        if len(gemini_text.strip()) >= MIN_USABLE_TEXT_CHARS:
            return gemini_text, "gemini-vision", model_for("pdf_vision")

    raise RuntimeError(
        "Free PDF extraction chain (Tesseract, Gemini vision) produced no "
        "usable text — every enabled free stage either failed or was "
        "rejected by its own quality check."
    )


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

    Tries pdfplumber's text layer first. A scanned document (no usable
    text layer) falls through the free chain — Tesseract, then Gemini
    vision — and only reaches the paid Claude API as a last resort, if
    every free stage failed or was disabled (`PDF_OCR_CLAUDE_LAST_RESORT_
    ENABLED`). The method and result are cached per content hash — see
    `_extraction_cache_path` — so a given document is never re-extracted
    (paid or free) more than once, and which method actually produced a
    document's text is recorded, not assumed. This cache check runs
    before any extraction method is even attempted, so the three PDFs
    already cached from earlier phases are never touched by this chain.
    """
    cached = _read_extraction_cache(source_document.content_hash)
    if cached is not None:
        return cached["text"]

    snapshot_file = resolve_snapshot_path(source_document.snapshot_path)
    text = _extract_pdf_text_via_pdfplumber(snapshot_file)

    if len(text.strip()) >= MIN_USABLE_TEXT_CHARS:
        _write_extraction_cache(source_document.content_hash, method="pdfplumber", text=text)
        return text

    try:
        text, method, model = extract_pdf_text_via_free_chain(snapshot_file)
        _write_extraction_cache(source_document.content_hash, method=method, text=text, model=model)
        return text
    except Exception:
        if not PDF_OCR_CLAUDE_LAST_RESORT_ENABLED:
            raise

    text = _extract_pdf_text_via_claude(snapshot_file)
    _write_extraction_cache(
        source_document.content_hash, method="claude-api", text=text, model=CLAUDE_MODEL
    )
    return text


def _table_rows_to_markdown(rows: list[list[str | None]]) -> str:
    grid = [[(cell or "").strip() for cell in row] for row in rows]
    grid = [row for row in grid if any(row)]
    if not grid:
        return ""
    header, *body = grid
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in body:
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")
    return "\n".join(lines)


def extract_pdf_blocks(source_document: SourceDocument) -> list[ExtractedBlock]:
    """Extract a PDF SourceDocument's content as an ordered list of
    prose/table blocks.

    pdfplumber's `extract_tables()` runs independently of `extract_text()`
    per page, and each table it finds becomes its own block, appended
    after that page's prose block — page-level document order, not exact
    pixel-level interleaving within a page (this corpus's one detected
    table sits alone on its page, so page-level ordering is exact here;
    see design.md).

    A scanned PDF (extracted via the Claude API, no text layer for
    pdfplumber to read tables from either) has no table detection
    available and is returned as prose blocks only, split on blank lines
    — the same granularity Phase 3's chunker used.
    """
    cached = _read_extraction_cache(source_document.content_hash)
    if cached is not None and cached["method"] == "claude-api":
        paragraphs = [p.strip() for p in cached["text"].split("\n\n") if p.strip()]
        return [ExtractedBlock("prose", p, None) for p in paragraphs]

    snapshot_file = resolve_snapshot_path(source_document.snapshot_path)
    blocks: list[ExtractedBlock] = []
    with pdfplumber.open(snapshot_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for paragraph in [p.strip() for p in text.split("\n\n") if p.strip()]:
                    blocks.append(ExtractedBlock("prose", paragraph, None))
            for table in page.extract_tables():
                markdown = _table_rows_to_markdown(table)
                if markdown:
                    blocks.append(ExtractedBlock("table", markdown, None))

    if not blocks:
        # No text layer and no cached Claude transcription yet (first
        # run) — fall back to the existing text-only extraction, which
        # itself triggers the Claude OCR path and caches the result.
        text = extract_pdf_text(source_document)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        blocks = [ExtractedBlock("prose", p, None) for p in paragraphs]

    return blocks
