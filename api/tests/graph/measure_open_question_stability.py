"""Tracks the open-question golden set's pass rate across N repeated
runs — a recorded metric, not a one-off measurement. See design.md's
"tool-selection instability" fix decision: the pass rate itself is a
*range* (8/7/7/8/9 at the time this was built), a real property of the
current system's live-model reliability on deliberately hard queries —
not a single number, and not something that should be rediscovered by
chance each time someone happens to re-run the suite by hand. Appending
every run to a tracked history file makes a later regression (or
improvement) visible over time, per explicit user instruction.

Run with:  python -m tests.graph.measure_open_question_stability [N]
(default N=5). Appends one JSON line per individual run to
stability_history.jsonl (git-tracked), plus prints a summary.
`test_stability_history.py` reads the latest recorded batch as a
lightweight, always-on regression check — it does not itself repeat
this N-run measurement (5x the live-API cost of the per-commit gate),
so re-running this script periodically (or after a change plausibly
affecting the agent's tool-use reliability) is what keeps the tracked
history current.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.chat.agent import answer_with_agent
from app.db.session import SessionLocal

from .golden_open_question_eval import evaluate_scenario
from .golden_open_questions import SCENARIOS

HISTORY_PATH = Path(__file__).parent / "stability_history.jsonl"


def run_once(db) -> dict[str, str | None]:
    """One full pass over all scenarios. Returns {scenario_name: reason}
    — reason is None for pass, "skipped" for a not-asserted scenario, or
    a failure string."""
    outcomes: dict[str, str | None] = {}
    for scenario in SCENARIOS:
        result = answer_with_agent(db, scenario["query"])
        outcomes[scenario["name"]] = evaluate_scenario(result, scenario)
    return outcomes


def measure(n: int = 5) -> list[dict]:
    db = SessionLocal()
    batch_id = datetime.now(timezone.utc).isoformat()
    entries = []
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        for i in range(n):
            t0 = time.perf_counter()
            outcomes = run_once(db)
            asserted = {k: v for k, v in outcomes.items() if v != "skipped"}
            passed = sum(1 for v in asserted.values() if v is None)
            total = len(asserted)
            failed_names = [k for k, v in asserted.items() if v is not None]
            entry = {
                "batch_id": batch_id,
                "run": i,
                "passed": passed,
                "total": total,
                "failed_scenarios": failed_names,
                "duration_s": round(time.perf_counter() - t0, 1),
            }
            entries.append(entry)
            f.write(json.dumps(entry) + "\n")
            f.flush()
            print(f"run {i}: {passed}/{total} — failed: {failed_names or 'none'}")
    return entries


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    entries = measure(n)
    rates = [e["passed"] for e in entries]
    print(f"\n{n} runs: {rates} (out of {entries[0]['total']} each)")
    print(f"Recorded to {HISTORY_PATH}")


if __name__ == "__main__":
    main()
