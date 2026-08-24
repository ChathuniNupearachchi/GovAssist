"""Reads the tracked open-question stability history (see
`measure_open_question_stability.py`) and asserts the latest recorded
batch's AVERAGE pass rate hasn't silently regressed below the floor
observed when this tracking was built. This does NOT itself re-run the
5x-repeated measurement — that stays a deliberately-invoked script (5x
the live-API cost of a normal test run) — it only checks whatever was
last recorded, so a regression is visible without paying that cost on
every commit.

Checked against the batch AVERAGE, not every individual run: the first
tracked batch itself included a single run at 5/9 (55.6%) alongside
four runs at 6-8/9 — this metric is genuinely noisy live-model
behavior, not a step function, so gating on the single worst run in a
5-run batch would false-alarm on ordinary variance already observed at
the moment this tracking was built. The average is what a real,
systemic regression would actually move.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

HISTORY_PATH = Path(__file__).parent / "stability_history.jsonl"

# Below the ~78% average observed across the runs that established this
# tracking (8, 5, 8, 8, 6 out of 9 → 35/45 = 77.8%) — a floor with
# margin under that average, not a target to celebrate meeting. See
# design.md's "tool-selection instability" fix decision.
MIN_ACCEPTABLE_AVERAGE_PASS_RATE = 0.6


def _latest_batch() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    lines = [
        json.loads(line)
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        return []
    latest_batch_id = lines[-1]["batch_id"]
    return [line for line in lines if line["batch_id"] == latest_batch_id]


def test_latest_stability_batch_average_has_not_regressed():
    batch = _latest_batch()
    if not batch:
        pytest.skip(
            "No stability history recorded yet — run "
            "`python -m tests.graph.measure_open_question_stability` first."
        )
    total_passed = sum(entry["passed"] for entry in batch)
    total_possible = sum(entry["total"] for entry in batch)
    average = total_passed / total_possible
    per_run = [f"{e['passed']}/{e['total']}" for e in batch]
    assert average >= MIN_ACCEPTABLE_AVERAGE_PASS_RATE, (
        f"Latest batch average {average:.1%} is below the "
        f"{MIN_ACCEPTABLE_AVERAGE_PASS_RATE:.0%} floor — per-run: {per_run}"
    )
