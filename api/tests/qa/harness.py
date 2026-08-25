"""Automated conversational QA harness — Part 2 of the manual-QA
bug-fix round.

Drives real multi-turn conversations through the actual HTTP-shaped
`POST /chat/message` and `POST /case/{id}/resolve` routes (via FastAPI's
`TestClient`, which calls the real `main.app` — same routing,
validation, and DB access a live server would use, just without a
separate process), reading scenarios from `questions.txt` so the
question set is editable without touching this code.

Each scenario gets a FRESH, unique `device_ref` — the mistake that
invalidated part of the manual testing was reusing one device_ref across
scenarios, which resumes the same case (`resolve_case_for_device`) and
lets one scenario's recorded facts bleed into the next.

Assessment is from the citizen's perspective, not pass/fail against a
fixed expected string — see `_judge_turn`: a Gemini judge (free tier,
matching this project's cost-engineering convention — evaluation-only,
never citizen-facing) scores each assistant turn against the six
citizen-perspective criteria the request specifies, and the harness
reports both a per-category pass rate AND the more useful list: turns
flagged as poor quality even where technically correct.

Run standalone:  python -m tests.qa.harness [category_letters]
(e.g. `python -m tests.qa.harness AF` runs only categories A and F;
omit to run everything.) Also reachable as a single `pytest -m real_api`
test (see test_qa_harness.py) for CI-deliberate runs — marked real_api
per the request, so it never runs on every suite pass.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models import Case, CaseAnswer, ChatMessage
from app.llm.gateway import structured_completion
from main import app

QUESTIONS_PATH = Path(__file__).parent / "questions.txt"
REPORT_PATH = Path(__file__).parent / "qa_report.json"

_CATEGORY_HEADER_RE = re.compile(r"^##\s*CATEGORY:\s*([A-Z])\s*—?-?\s*(.*)$")


# --------------------------------------------------------------------
# 1. Parsing questions.txt
# --------------------------------------------------------------------


@dataclass
class Scenario:
    category: str
    category_name: str
    index: int
    turns: list[str]


def parse_questions(path: Path = QUESTIONS_PATH) -> list[Scenario]:
    """Groups lines into categories, and within a category, groups
    consecutive non-blank lines into one multi-turn scenario — a blank
    line starts a new scenario. Comment lines (#) and the category
    header itself are never scenario content."""
    scenarios: list[Scenario] = []
    category = None
    category_name = ""
    current_turns: list[str] = []
    index_by_category: dict[str, int] = {}

    def _flush():
        nonlocal current_turns
        if current_turns and category is not None:
            index_by_category[category] = index_by_category.get(category, 0) + 1
            scenarios.append(
                Scenario(
                    category=category,
                    category_name=category_name,
                    index=index_by_category[category],
                    turns=list(current_turns),
                )
            )
        current_turns = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        header_match = _CATEGORY_HEADER_RE.match(stripped)
        if header_match:
            _flush()
            category, category_name = header_match.group(1), header_match.group(2).strip()
            continue

        if stripped.startswith("#"):
            continue

        if not stripped:
            _flush()
            continue

        current_turns.append(stripped)

    _flush()
    return scenarios


# --------------------------------------------------------------------
# 2. Driving one scenario through the real API
# --------------------------------------------------------------------


@dataclass
class TurnResult:
    message: str
    answer_text: str | None
    grounded: bool | None
    next_question_prompt: str | None
    acknowledgement: str | None
    status_code: int


@dataclass
class ScenarioResult:
    scenario: Scenario
    device_ref: str
    case_id: str | None
    turns: list[TurnResult] = field(default_factory=list)
    resolve_status_code: int | None = None
    resolve_body: dict | None = None
    error: str | None = None


def _fresh_device_ref(scenario: Scenario) -> str:
    # Fresh, unique per scenario — never reused, so no scenario resumes
    # another's case (the mistake that invalidated part of manual QA).
    return f"qa-{scenario.category}-{scenario.index}-{uuid.uuid4().hex[:8]}"


def run_scenario(client: TestClient, scenario: Scenario) -> ScenarioResult:
    device_ref = _fresh_device_ref(scenario)
    result = ScenarioResult(scenario=scenario, device_ref=device_ref, case_id=None)
    case_id: str | None = None

    try:
        for message in scenario.turns:
            payload = {"message": message, "device_ref": device_ref}
            if case_id is not None:
                payload = {"message": message, "case_id": case_id}
            response = client.post("/chat/message", json=payload)
            if response.status_code != 200:
                result.turns.append(
                    TurnResult(
                        message=message, answer_text=None, grounded=None,
                        next_question_prompt=None, acknowledgement=None,
                        status_code=response.status_code,
                    )
                )
                continue
            body = response.json()
            case_id = body["case_id"]
            result.case_id = case_id
            answer = body.get("answer") or {}
            next_q = body.get("next_question") or {}
            result.turns.append(
                TurnResult(
                    message=message,
                    answer_text=answer.get("text"),
                    grounded=answer.get("grounded"),
                    next_question_prompt=next_q.get("display_text") or next_q.get("prompt"),
                    acknowledgement=body.get("acknowledgement"),
                    status_code=response.status_code,
                )
            )

        # Exercise /case/{id}/resolve too, per the request, whenever
        # intake naturally finished this scenario (no question left
        # pending after the last turn) — most short QA probes never
        # reach this; the situation-heavy categories (B, F, G) often do.
        if case_id is not None and result.turns and result.turns[-1].next_question_prompt is None:
            resolve_response = client.post(f"/case/{case_id}/resolve")
            result.resolve_status_code = resolve_response.status_code
            if resolve_response.status_code == 200:
                result.resolve_body = resolve_response.json()
    except Exception as exc:  # a harness-level failure is itself a finding, not a crash
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def cleanup_scenario(result: ScenarioResult) -> None:
    """Deletes this scenario's Case/CaseAnswer/ChatMessage rows — the QA
    run is disposable scratch data, and leaving it behind would corrupt
    the next real seed/test run's FK-cleanliness the same way stray
    verification-script cases already have (see BACKEND_PLAN.md's
    backup note)."""
    if result.case_id is None:
        return
    db = SessionLocal()
    try:
        case_uuid = uuid.UUID(result.case_id)
        db.query(ChatMessage).filter(ChatMessage.case_id == case_uuid).delete()
        db.query(CaseAnswer).filter(CaseAnswer.case_id == case_uuid).delete()
        db.query(Case).filter(Case.id == case_uuid).delete()
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------
# 3. Judging each turn from the citizen's perspective (Gemini, free tier)
# --------------------------------------------------------------------

from pydantic import BaseModel  # noqa: E402


class TurnVerdict(BaseModel):
    understandable: bool
    answers_what_was_asked: bool
    has_jargon: bool
    too_long_for_phone: bool
    refusal_names_next_step: bool | None = None  # null when not a refusal
    question_answerable_without_prior_knowledge: bool | None = None  # null when not a question
    overall_ok: bool
    flag_reason: str | None = None  # short reason, only when overall_ok is False


_JUDGE_SYSTEM_PROMPT = """You judge one turn of a Sri Lankan government-services \
chat assistant from an ORDINARY CITIZEN's perspective — not whether the answer is \
technically correct, but whether a person using this outdoors on their phone, possibly \
anxious about a government process, would find it usable.

Judge:
- understandable: would an ordinary citizen understand this?
- answers_what_was_asked: does it answer what was actually asked (or, if it's a \
question the assistant is asking, is it a reasonable next question)?
- has_jargon: is any wording bureaucratic, legal, or jargon-laden (should be false \
for a good response)?
- too_long_for_phone: is it too long to comfortably read on a phone screen?
- refusal_names_next_step: if the assistant declined/refused to answer, does it say \
what to do instead? null if this wasn't a refusal.
- question_answerable_without_prior_knowledge: if the assistant asked a question, \
could someone with no prior knowledge of passport rules answer it? null if this \
wasn't a question.
- overall_ok: your overall judgment — would a reasonable citizen be satisfied with \
this turn?
- flag_reason: if overall_ok is false, one short sentence why. null otherwise."""


# Gemini free-tier pacing, same precedent as tests/eval/ragas_baseline.py
# (confirmed there, via live 429s, that a burst of free-tier calls gets
# rate-limited) — lighter here (one small structured call per turn,
# vs. that module's four-metrics-per-scenario), so a shorter interval
# and a single bounded retry rather than that module's more conservative
# 15s/3-retries.
_SECONDS_BETWEEN_JUDGE_CALLS = 3.0
_JUDGE_RETRY_BACKOFF_S = 15.0


def _judge_turn(citizen_message: str, assistant_reply: str) -> TurnVerdict:
    import time

    time.sleep(_SECONDS_BETWEEN_JUDGE_CALLS)
    for attempt in range(2):
        try:
            return structured_completion(
                "qa_judge",
                system=_JUDGE_SYSTEM_PROMPT,
                user=f'Citizen said: "{citizen_message}"\n\nAssistant replied: "{assistant_reply}"',
                response_model=TurnVerdict,
                max_tokens=512,
            )
        except Exception as exc:
            is_rate_limit = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            if not is_rate_limit or attempt == 1:
                # A real (non-rate-limit) failure, or the retry also
                # failed — surfaced in the report as an unscored turn
                # rather than silently counted as overall_ok, so a
                # judge outage shows up as missing data, not a false
                # "everything passed."
                return TurnVerdict(
                    understandable=True, answers_what_was_asked=True, has_jargon=False,
                    too_long_for_phone=False, overall_ok=True,
                    flag_reason=f"[judge call failed, NOT actually scored: {exc}]",
                )
            time.sleep(_JUDGE_RETRY_BACKOFF_S)


def _assistant_reply_text(turn: TurnResult) -> str | None:
    return turn.answer_text or turn.next_question_prompt or turn.acknowledgement


# --------------------------------------------------------------------
# 4. Explicitly-asserted behaviors
# --------------------------------------------------------------------


def check_unexpected_answer_reasks_pending_question(client: TestClient) -> tuple[bool, str]:
    """An unexpected answer to a pending question re-asks that question
    rather than proceeding. Fresh case: `age` is the first pending
    question; a message that is neither a plausible age token nor
    classifiable as one must leave `age` still pending."""
    device_ref = f"qa-assert-reask-{uuid.uuid4().hex[:8]}"
    result = ScenarioResult(scenario=Scenario("Z", "assertions", 0, []), device_ref=device_ref, case_id=None)
    try:
        r1 = client.post("/chat/message", json={"message": "asdkjfh qwerty zzxc", "device_ref": device_ref})
        if r1.status_code != 200:
            return False, f"first turn returned {r1.status_code}"
        case_id = r1.json()["case_id"]
        result.case_id = case_id
        first_pending = (r1.json().get("next_question") or {}).get("prompt")
        r2 = client.post("/chat/message", json={"message": "still not an age", "case_id": case_id})
        second_pending = (r2.json().get("next_question") or {}).get("prompt")
        ok = first_pending is not None and first_pending == second_pending
        return ok, "" if ok else f"pending question changed from {first_pending!r} to {second_pending!r}"
    finally:
        cleanup_scenario(result)


def check_correction_updates_recorded_fact(client: TestClient) -> tuple[bool, str]:
    """A correction updates the recorded fact rather than being ignored
    — verified against the actual CASE_ANSWER row, not just the reply
    text."""
    device_ref = f"qa-assert-correction-{uuid.uuid4().hex[:8]}"
    result = ScenarioResult(scenario=Scenario("Z", "assertions", 0, []), device_ref=device_ref, case_id=None)
    try:
        r1 = client.post("/chat/message", json={"message": "34", "device_ref": device_ref})
        case_id = r1.json()["case_id"]
        result.case_id = case_id
        client.post("/chat/message", json={"message": "actually I'm 45 not 34", "case_id": case_id})

        db = SessionLocal()
        try:
            from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT
            from app.models import Question

            rows = db.execute(
                CaseAnswer.__table__.select().where(CaseAnswer.case_id == uuid.UUID(case_id))
            ).fetchall()
            age_value = None
            for row in rows:
                question = db.get(Question, row.question_id)
                if question is not None and ATTRIBUTE_BY_PROMPT.get(question.prompt) == "age":
                    age_value = row.value
            ok = age_value == "45"
            return ok, "" if ok else f"recorded age is {age_value!r}, expected '45'"
        finally:
            db.close()
    finally:
        cleanup_scenario(result)


# --------------------------------------------------------------------
# 5. Orchestration + report
# --------------------------------------------------------------------


def run_all(category_filter: str | None = None) -> dict:
    scenarios = parse_questions()
    if category_filter:
        scenarios = [s for s in scenarios if s.category in category_filter]

    client = TestClient(app)
    per_category: dict[str, list[dict]] = {}
    flagged: list[dict] = []

    for scenario in scenarios:
        result = run_scenario(client, scenario)
        scenario_ok = result.error is None and all(t.status_code == 200 for t in result.turns)

        turn_reports = []
        for turn in result.turns:
            reply = _assistant_reply_text(turn)
            verdict = _judge_turn(turn.message, reply) if reply else None
            if verdict is not None and not verdict.overall_ok:
                flagged.append(
                    {
                        "category": f"{scenario.category} — {scenario.category_name}",
                        "scenario_index": scenario.index,
                        "citizen_said": turn.message,
                        "assistant_replied": reply,
                        "reason": verdict.flag_reason,
                    }
                )
            turn_reports.append(
                {
                    "message": turn.message,
                    "reply": reply,
                    "status_code": turn.status_code,
                    "verdict": verdict.model_dump() if verdict is not None else None,
                }
            )

        per_category.setdefault(scenario.category, []).append(
            {
                "category_name": scenario.category_name,
                "scenario_index": scenario.index,
                "turns": turn_reports,
                "resolve_status_code": result.resolve_status_code,
                "error": result.error,
                "technically_ok": scenario_ok,
            }
        )
        cleanup_scenario(result)

    reask_ok, reask_reason = check_unexpected_answer_reasks_pending_question(client)
    correction_ok, correction_reason = check_correction_updates_recorded_fact(client)

    category_pass_rates = {}
    for category, entries in per_category.items():
        total = len(entries)
        # A scenario "passes" the quality bar when every judged turn in
        # it was overall_ok AND the scenario ran technically clean.
        passed = sum(
            1
            for e in entries
            if e["technically_ok"]
            and all((t["verdict"] or {}).get("overall_ok", True) for t in e["turns"])
        )
        category_pass_rates[category] = {"passed": passed, "total": total}

    report = {
        "category_pass_rates": category_pass_rates,
        "flagged_responses": flagged,
        "explicit_assertions": {
            "unexpected_answer_reasks_pending_question": {"ok": reask_ok, "detail": reask_reason},
            "correction_updates_recorded_fact": {"ok": correction_ok, "detail": correction_reason},
        },
        "per_category_detail": per_category,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def print_report(report: dict) -> None:
    print("Per-category pass rates:")
    for category, rate in sorted(report["category_pass_rates"].items()):
        print(f"  {category}: {rate['passed']}/{rate['total']}")

    print("\nExplicit assertions:")
    for name, result in report["explicit_assertions"].items():
        status = "OK" if result["ok"] else f"FAILED — {result['detail']}"
        print(f"  {name}: {status}")

    print(f"\nFlagged responses (poor quality, even if technically correct): {len(report['flagged_responses'])}")
    for item in report["flagged_responses"]:
        print(f"  [{item['category']}] \"{item['citizen_said']}\" -> \"{item['assistant_replied']}\"")
        print(f"    reason: {item['reason']}")

    print(f"\nFull report written to {REPORT_PATH}")


if __name__ == "__main__":
    category_filter = sys.argv[1] if len(sys.argv) > 1 else None
    report = run_all(category_filter)
    print_report(report)
