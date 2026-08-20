"""HTML structured extraction from a saved snapshot (never from the live
fetch response — chunking always reads the persisted snapshot).

Phase 6.6 note: the request that drove this phase assumed `<table>`
elements would carry the corpus's fee/hours data generally. Direct
inspection of all 5 approved HTML snapshots found real `<table>` markup
in exactly one of them — `pages_e.php?id=10`'s alterations fee table
(7 rows x 3 columns). The other structured content this phase targets —
`pages_e.php?id=8`'s processing-fee lines and `pages_e.php?id=7`'s
working-hours lines — is marked up as `<p>Label - Value<br>Label -
Value</p>` pairs and `<ul>/<li>` lists under a bold question paragraph,
not `<table>`. Detecting only literal `<table>` tags would leave those
two pages exactly as flattened as before, missing this phase's two
headline DONE WHEN criteria. So extraction here detects three structural
shapes, not one: real `<table>` elements, `<ul>/<ol>` lists, and
paragraphs whose lines are `Label - Value` pairs (the fee-line pattern) —
each becomes its own table/list block. See design.md's "Table detection
generalizes to the corpus's real structure" decision for the record.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from app.ingestion.blocks import ExtractedBlock
from app.models import SourceDocument
from app.scraper.fetch import resolve_snapshot_path

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK_TAGS = _HEADING_TAGS | {"p", "ul", "ol", "table"}

# "Normal Basis -  LKR. 10,000.00" / "Urgent Basis - LKR.20,000.00" —
# a label, a dash, and a value that names a currency or amount.
_FEE_LINE_RE = re.compile(r"^(.{2,60}?)\s*[-–—]\s*(LKR[.\s]*[\d,]+(?:\.\d+)?.*)$", re.I)


def _decompose_boilerplate(soup: BeautifulSoup) -> None:
    """Strip the site-wide nav/footer boilerplate — see prior phase's
    finding: exactly 212 words removed per page, every time."""
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()
    bottom_section = soup.find("section", id="bottom")
    if bottom_section is not None:
        bottom_section.decompose()
    footer = soup.find("footer")
    if footer is not None:
        footer.decompose()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _raw_lines(tag: Tag) -> list[str]:
    """Text content of `tag`, split on <br> boundaries — needed because
    `get_text()` alone loses the line breaks a fee block's meaning
    depends on."""
    lines: list[str] = []
    current: list[str] = []
    for node in tag.descendants:
        if isinstance(node, NavigableString):
            current.append(str(node))
        elif getattr(node, "name", None) == "br":
            lines.append(_clean("".join(current)))
            current = []
    lines.append(_clean("".join(current)))
    return [line for line in lines if line]


def _heading_text(p_tag: Tag) -> str | None:
    """A `<p>` whose entire content lives inside a single `<strong>`/`<b>`
    child acts as a heading in this site's markup (e.g. "What are the
    processing fees...?"), even though it isn't an `<h#>` tag."""
    emphasis = p_tag.find(["strong", "b"])
    if emphasis is None:
        return None
    full_text = _clean(p_tag.get_text(" "))
    emphasis_text = _clean(emphasis.get_text(" "))
    if full_text and full_text == emphasis_text:
        return full_text
    return None


def _fee_rows(p_tag: Tag) -> list[tuple[str, str]] | None:
    """A `<p>` made of >=2 "Label - Value" lines, each naming a fee."""
    lines = _raw_lines(p_tag)
    if len(lines) < 2:
        return None
    rows = []
    for line in lines:
        match = _FEE_LINE_RE.match(line)
        if not match:
            return None
        rows.append((match.group(1).strip(), match.group(2).strip()))
    return rows


def _fee_rows_to_markdown(rows: list[tuple[str, str]]) -> str:
    lines = ["| Basis | Fee |", "| --- | --- |"]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    return "\n".join(lines)


def _table_to_markdown(table_tag: Tag) -> str:
    grid = []
    for row in table_tag.find_all("tr"):
        cells = [_clean(cell.get_text(" ")) for cell in row.find_all(["th", "td"])]
        if any(cells):
            grid.append(cells)
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


def _li_own_text(li: Tag) -> str:
    """A `<li>`'s own text, excluding any nested `<ul>/<ol>` (rendered
    separately, indented, by the caller)."""
    parts = []
    for child in li.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif child.name not in ("ul", "ol"):
            parts.append(child.get_text(" "))
    return _clean("".join(parts))


def _list_to_markdown(list_tag: Tag, indent: int = 0) -> str:
    ordered = list_tag.name == "ol"
    lines = []
    for index, li in enumerate(list_tag.find_all("li", recursive=False), start=1):
        own_text = _li_own_text(li)
        bullet = f"{index}." if ordered else "-"
        if own_text:
            lines.append("  " * indent + f"{bullet} {own_text}")
        for nested in li.find_all(["ul", "ol"], recursive=False):
            nested_markdown = _list_to_markdown(nested, indent + 1)
            if nested_markdown:
                lines.append(nested_markdown)
    return "\n".join(lines)


def _is_nested_inside_block(tag: Tag, soup: BeautifulSoup) -> bool:
    """True if an ancestor of `tag` (other than the document root) is
    itself one of the block tags this pass already handles — used to
    avoid double-processing a `<ul>` nested inside a `<table>` cell or a
    `<p>` nested inside another block."""
    for parent in tag.parents:
        if parent is soup:
            break
        if parent.name in _BLOCK_TAGS:
            return True
    return False


def extract_html_blocks(source_document: SourceDocument) -> list[ExtractedBlock]:
    """Extract an html SourceDocument's content as an ordered list of
    prose/table/list blocks, each carrying the nearest preceding
    heading."""
    snapshot_file = resolve_snapshot_path(source_document.snapshot_path)
    html = snapshot_file.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    _decompose_boilerplate(soup)

    heading: str | None = None
    blocks: list[ExtractedBlock] = []

    for el in soup.find_all(list(_BLOCK_TAGS)):
        if _is_nested_inside_block(el, soup):
            continue

        if el.name in _HEADING_TAGS:
            text = _clean(el.get_text(" "))
            if text:
                blocks.append(ExtractedBlock("prose", text, heading))
                heading = text
            continue

        if el.name == "table":
            markdown = _table_to_markdown(el)
            if markdown:
                blocks.append(ExtractedBlock("table", markdown, heading))
            continue

        if el.name in ("ul", "ol"):
            markdown = _list_to_markdown(el)
            if markdown:
                blocks.append(ExtractedBlock("list", markdown, heading))
            continue

        # el.name == "p"
        text = _clean(el.get_text(" "))
        if not text:
            continue

        heading_text = _heading_text(el)
        if heading_text:
            blocks.append(ExtractedBlock("prose", heading_text, heading))
            heading = heading_text
            continue

        fee_rows = _fee_rows(el)
        if fee_rows:
            blocks.append(ExtractedBlock("table", _fee_rows_to_markdown(fee_rows), heading))
            continue

        blocks.append(ExtractedBlock("prose", text, heading))

    return blocks


def extract_html_text(source_document: SourceDocument) -> str:
    """Flattened text for callers that don't need block structure (kept
    for anything reading a document's plain content outside the chunker,
    e.g. change-detection hashing)."""
    return "\n\n".join(block.text for block in extract_html_blocks(source_document))
