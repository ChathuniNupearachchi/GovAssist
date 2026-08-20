"""Retrieval calibration harness — phase-6-6-to-6-10-rag-quality-and-sessions.

Runs the nine-query calibration set (six genuinely in the corpus, three
genuinely absent) against the current retrieval implementation and
reports the top-1 distance/score for each, plus which source document it
matched. Re-run after every phase (6.6, 6.7, and 6.8 if it proceeds) so
each phase's effect is measured, not assumed — see design.md's
calibration table, which this script's output is transcribed into by
hand after each run.

This module intentionally calls `_search` directly rather than
`retrieve`, so it reports the raw top-1 distance regardless of the
current WEAK_MATCH_THRESHOLD — the threshold is what gets *chosen* from
this data, not baked into how the data is measured.

Run with:  python -m app.rag.calibration
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.session import SessionLocal
from app.rag.retrieval import _search

CALIBRATION_QUERIES: list[tuple[str, str]] = [
    # (query, expected) — expected is "accept" (in corpus) or "reject" (absent)
    ("What is the fee for a name change amendment?", "accept"),
    ("What are the working hours at the Head Office?", "accept"),
    ("What is an authorised photo studio?", "accept"),
    ("What documents do I need for a dual citizen passport?", "accept"),
    ("What is Form K-35A?", "accept"),
    ("What happens under section 19(2)?", "accept"),
    ("How do I renew my driving license?", "reject"),
    ("What is the weather in Colombo?", "reject"),
    ("How do I apply for a visa to Australia?", "reject"),
]


@dataclass(frozen=True)
class CalibrationRow:
    query: str
    expected: str
    top_score: float | None  # fused RRF score post-6.7; cosine distance pre-6.7
    top_distance: float | None  # raw cosine distance — n/a pre-6.7 (not tracked separately then)
    top_source_url: str | None


def measure() -> list[CalibrationRow]:
    """Measures against whatever `_search` currently implements — cosine-
    only pre-6.7, hybrid RRF from 6.7 onward. The score's meaning (lower-
    is-better distance vs. higher-is-better fused score) is whatever
    `_search`'s current docstring says; this harness doesn't normalize
    across phases, by design — see design.md's calibration table, which
    records each phase's own metric alongside its own values."""
    db = SessionLocal()
    rows: list[CalibrationRow] = []
    try:
        for query, expected in CALIBRATION_QUERIES:
            results = _search(db, query, top_k=1)
            if results:
                top = results[0]
                rows.append(
                    CalibrationRow(
                        query=query,
                        expected=expected,
                        top_score=round(top.score, 6),
                        top_distance=round(top.vector_distance, 4),
                        top_source_url=top.source_document.source_url,
                    )
                )
            else:
                rows.append(
                    CalibrationRow(
                        query=query, expected=expected, top_score=None, top_distance=None, top_source_url=None
                    )
                )
    finally:
        db.close()
    return rows


def print_table(rows: list[CalibrationRow]) -> None:
    print(f"{'Query':<58} {'Expect':<7} {'Score':<10} {'Distance':<9} Top source")
    print("-" * 120)
    for row in rows:
        score = f"{row.top_score:.6f}" if row.top_score is not None else "n/a"
        distance = f"{row.top_distance:.4f}" if row.top_distance is not None else "n/a"
        source = row.top_source_url or "n/a"
        print(f"{row.query:<58} {row.expected:<7} {score:<10} {distance:<9} {source}")


def main() -> None:
    rows = measure()
    print_table(rows)


if __name__ == "__main__":
    main()
