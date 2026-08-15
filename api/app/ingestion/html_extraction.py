"""HTML text extraction from a saved snapshot (never from the live fetch
response — chunking always reads the persisted snapshot)."""

from bs4 import BeautifulSoup

from app.models import SourceDocument
from app.scraper.fetch import resolve_snapshot_path


def extract_html_text(source_document: SourceDocument) -> str:
    """Extract visible text from an html SourceDocument's saved snapshot."""
    snapshot_file = resolve_snapshot_path(source_document.snapshot_path)
    html = snapshot_file.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
