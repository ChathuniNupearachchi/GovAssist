"""Pytest entry point for the conversational QA harness (Part 2 of the
manual-QA bug-fix round) — marked `real_api` so it runs deliberately
(`pytest -m real_api` or `python -m tests.qa.harness`), never on every
suite pass: it drives dozens of real multi-turn conversations through
the live Claude/Gemini APIs, and judges every reply with a Gemini judge
call, which is neither free nor fast.

Asserts only the two behaviors the request calls out explicitly — an
unexpected answer to a pending question re-asks it, and a correction
updates the recorded fact — as hard pass/fail. The broader category
pass-rates and flagged-response list are informational (`design.md`'s
"report per-category pass rates... the second list is the more useful
one" — a judged, graded assessment, not a single bar to clear), printed
for a human to read, not asserted against a fixed threshold.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from tests.qa.harness import (
    check_correction_updates_recorded_fact,
    check_unexpected_answer_reasks_pending_question,
    print_report,
    run_all,
)

pytestmark = pytest.mark.real_api


def test_unexpected_answer_reasks_pending_question():
    client = TestClient(app)
    ok, detail = check_unexpected_answer_reasks_pending_question(client)
    assert ok, detail


def test_correction_updates_recorded_fact():
    client = TestClient(app)
    ok, detail = check_correction_updates_recorded_fact(client)
    assert ok, detail


def test_full_qa_harness_report():
    """Runs every category, prints the per-category pass rates and the
    flagged-response list. Not asserted against a threshold — this is a
    quality report for a human to read (`tests/qa/qa_report.json` also
    gets the full detail), not a binary regression gate."""
    report = run_all()
    print_report(report)
