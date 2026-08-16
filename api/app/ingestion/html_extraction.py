"""HTML text extraction from a saved snapshot (never from the live fetch
response — chunking always reads the persisted snapshot)."""

from bs4 import BeautifulSoup

from app.models import SourceDocument
from app.scraper.fetch import resolve_snapshot_path


def extract_html_text(source_document: SourceDocument) -> str:
    """Extract visible text from an html SourceDocument's saved snapshot.

    Strips navigation and footer boilerplate before returning text, so it
    never reaches the chunker — see phase-5-rag-layer's design.md. Every
    page on immigration.gov.lk carries an identical structure:
      - <nav>: the site-wide menu (128 words, identical on every page)
      - <section id="bottom">: quick links / related links / contact
        details (84 words, identical on every page)
      - <footer>: copyright + a "Last Update" date that changes on every
        fetch, which would otherwise churn chunk text/hashes for no
        citizen-relevant reason
    Confirmed by direct measurement across all 5 HTML documents: exactly
    212 words removed per page in every case, with the studio_e.php page
    (275 words total) dropping to 63 — down to its actual content.
    """
    snapshot_file = resolve_snapshot_path(source_document.snapshot_path)
    html = snapshot_file.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav"]):
        tag.decompose()
    bottom_section = soup.find("section", id="bottom")
    if bottom_section is not None:
        bottom_section.decompose()
    footer = soup.find("footer")
    if footer is not None:
        footer.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
