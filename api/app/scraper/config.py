"""Scraper target configuration — Phase 3, renewal-relevant pages.

immigration.gov.lk has no dedicated "renewal" page; renewal-relevant
content is spread across these five pages. See the
phase-3-ingestion-pipeline change's proposal.md for the research behind
this list, including why pages_e.php?id=11 is deliberately excluded.
"""

TARGET_PAGES = [
    "https://www.immigration.gov.lk/pages_e.php?id=7",
    "https://www.immigration.gov.lk/pages_e.php?id=8",
    "https://www.immigration.gov.lk/pages_e.php?id=9",
    "https://www.immigration.gov.lk/pages_e.php?id=10",
    "https://www.immigration.gov.lk/studio_e.php",
]
