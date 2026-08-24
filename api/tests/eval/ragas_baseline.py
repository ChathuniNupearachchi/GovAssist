"""RAGAS baseline — langgraph-orchestration-branch Task Group 4.

Computes context precision, context recall, faithfulness, and answer
relevancy against the 7 grounded, reference-bearing scenarios of the
open-question golden set (`tests/graph/golden_open_questions.py`) — the
3 refusal/ambiguous scenarios (8-10) aren't part of this dataset, since
RAGAS's metrics score generation quality, not refusal correctness
(already checked by `test_golden_open_questions.py`).

Judge LLM: Gemini's free tier (`gemini-flash-lite-latest` by default,
`LLM_MODEL_RAGAS_JUDGE` env var to override) — langgraph-orchestration-
branch's cost-engineering decision ("free tiers wherever the output is
not citizen-facing"): the judge scores generation quality, it is not
itself the citizen-facing output, so it does not need to be Claude —
RAGAS is provider-agnostic and the judge does not need to match the
system under test. Embeddings: the same local, CPU-only
`all-MiniLM-L6-v2` this project already uses for retrieval — no new
embedding dependency, no external API call for embeddings either.

Reached via the OpenAI-compatible endpoint Google publishes for Gemini
(`https://generativelanguage.googleapis.com/v1beta/openai/`), not
`ragas`'s own `provider="google"` path — `ragas.llms.adapters.
auto_detect_adapter`'s own source comment flags a live upstream bug
in the newer google-genai-native `instructor` integration ("known
upstream issue with instructor sending invalid safety settings
(HARM_CATEGORY_JAILBREAK)... Workaround: Use OpenAI-compatible endpoint
with Gemini base URL instead" — ragas's own maintainers' documented
fix, not a workaround invented here). `provider="openai"` with an
`AsyncOpenAI` client pointed at that base URL and `GEMINI_API_KEY` as
the bearer token gets the well-trodden OpenAI-shaped `instructor` code
path (the same one this project's `app.llm.gateway` doesn't need,
since that module talks to Gemini through LiteLLM's own native
translation instead — this file predates that choice and Gemini's
OpenAI-compat endpoint is what `ragas`'s adapter layer actually
supports cleanly today).

Run with:  python -m tests.eval.ragas_baseline [N]
(N = repeat count per scenario, default 1 — RAGAS scores are graded/
continuous, not the golden set's binary pass/fail, so this is about a
representative baseline, not the same 5x stability tracking Task Group
3 built for the binary metric.)

Appends one JSON line per run to `ragas_history.jsonl` (git-tracked),
same tracked-metric convention as Task Group 3's stability history —
per design.md's "measured, not assumed" pattern applied consistently.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import openai

from . import ragas_compat  # noqa: F401 — side-effect import, must run before any ragas import

from ragas.embeddings import HuggingFaceEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, ContextPrecisionWithReference, ContextRecall, Faithfulness

from app.chat.agent import answer_with_agent
from app.db.session import SessionLocal

from tests.graph.golden_open_questions import SCENARIOS

HISTORY_PATH = Path(__file__).parent / "ragas_history.jsonl"

JUDGE_MODEL = os.environ.get("LLM_MODEL_RAGAS_JUDGE", "gemini-flash-lite-latest")
GEMINI_OPENAI_COMPAT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Only the scenarios with a hand-written reference answer — see
# golden_open_questions.py's module docstring.
RAGAS_SCENARIOS = [s for s in SCENARIOS if "reference" in s]


def _retrieved_contexts_from_trace(trace) -> list[str]:
    """Pulls the grounding "context" out of every tool call in this turn's
    trace — not just `retrieve_documents`'s chunk text.

    Confirmed directly (not assumed) that restricting this to
    `retrieve_documents` alone was wrong: scenarios 4, 5, and 7 of
    `golden_open_questions.py` are answered purely through `get_fee` /
    `find_office` — CLAUDE.md's rules-engine mechanism, not RAG — with
    zero `retrieve_documents` calls in their trace. Reference-trace-only
    scoring produced `retrieved_contexts == [""]` for those, and RAGAS's
    context precision/recall/faithfulness (which score "is the response
    grounded in this context") scored a flat 0.0 on all three — not
    because the answer was wrong (verified correct, and this project's own
    `_verify_submission` had already checked it against the real tool
    result before the agent could submit it), but because the instrument
    had nothing to compare against. A tool result IS the grounding source
    for a rules-engine-answered turn, exactly parallel to a retrieved
    chunk for a RAG-answered one — CLAUDE.md draws that line explicitly
    ("Open questions → an agent with tools... every such value in its
    answer is verified against what a tool call actually returned that
    turn"). So every tool's JSON result is serialized into a context
    string here, not only `retrieve_documents`'s."""
    contexts: list[str] = []
    for record in trace:
        if record.tool == "retrieve_documents":
            for chunk in record.result.get("chunks", []):
                contexts.append(chunk["text"])
        else:
            contexts.append(f"{record.tool} result: {json.dumps(record.result, default=str)}")
    return contexts


def _run_agent_for_ragas(db) -> list[dict]:
    """Runs the agent once per RAGAS scenario, returning one dict per
    scenario with the fields every metric needs. A scenario the agent
    refuses (result is None) is recorded with empty response/contexts —
    every metric scores it as poorly as a refusal-when-grounded-was-
    expected should, rather than being silently skipped."""
    samples = []
    for scenario in RAGAS_SCENARIOS:
        result = answer_with_agent(db, scenario["query"])
        if result is None:
            samples.append(
                {
                    "name": scenario["name"],
                    "user_input": scenario["query"],
                    "response": "",
                    "retrieved_contexts": [],
                    "reference": scenario["reference"],
                }
            )
            continue
        samples.append(
            {
                "name": scenario["name"],
                "user_input": scenario["query"],
                "response": result.text,
                "retrieved_contexts": _retrieved_contexts_from_trace(result.trace) or [""],
                "reference": scenario["reference"],
            }
        )
    return samples


def _judge_llm():
    """Builds the ragas judge LLM for Gemini's free tier, via `instructor`'s
    OpenAI code path pointed at Gemini's OpenAI-compatible endpoint — see
    the module docstring for why (a documented upstream bug in the
    native google-genai `instructor` integration, flagged by ragas's own
    `auto_detect_adapter` source comment).

    `agenerate()` requires an async client the same way the earlier
    Claude judge did (`InstructorLLM._check_client_async`) — `AsyncOpenAI`
    satisfies that directly; no client-shape workaround needed here (the
    `AsyncAnthropic` fix and the temperature/top_p/thinking stripping
    this function used to need were all Anthropic-specific — Gemini's
    OpenAI-compat endpoint accepts standard OpenAI chat-completion
    parameters without any of those three rejections).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — required for the RAGAS judge "
            "(langgraph-orchestration-branch's cost-engineering decision "
            "moved judge scoring off Claude onto Gemini's free tier). "
            "Add it to api/.env."
        )
    client = openai.AsyncOpenAI(api_key=api_key, base_url=GEMINI_OPENAI_COMPAT_BASE_URL)
    llm = llm_factory(model=JUDGE_MODEL, provider="openai", client=client)
    return llm


# Confirmed directly (not assumed), via live 429s: `gemini-3.6-flash`
# (this project's first choice, since it's what the API itself suggested
# on a 404 for the older `gemini-2.0-flash`) caps the free tier at 5
# requests/minute AND only 20 requests/DAY per project per model —
# nowhere near enough for a 28-call run (7 scenarios x 4 metrics), let
# alone repeated runs. Switched to `gemini-flash-lite-latest`, a
# lighter, more standard free-tier model with materially more daily
# headroom. Calls are still spaced 15s apart and retried once on a 429
# that slips through regardless of which model is configured — a
# per-minute cap is a reasonable assumption for any Gemini free-tier
# model even where a specific daily figure hasn't been independently
# confirmed for it the way `gemini-3.6-flash`'s was.
_SECONDS_BETWEEN_JUDGE_CALLS = 15
_RATE_LIMIT_RETRY_BACKOFF_S = 30
_RATE_LIMIT_MAX_RETRIES = 3


async def _judged(coro_factory):
    """Runs one judge-metric `.ascore()` call, paced to stay under the
    free tier's rate limit, with a bounded retry on a 429 that still
    slips through (network jitter, a burst from a prior run) rather than
    failing the whole batch over one transient rate-limit hit."""
    await asyncio.sleep(_SECONDS_BETWEEN_JUDGE_CALLS)
    for attempt in range(_RATE_LIMIT_MAX_RETRIES + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            is_rate_limit = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            if not is_rate_limit or attempt == _RATE_LIMIT_MAX_RETRIES:
                raise
            await asyncio.sleep(_RATE_LIMIT_RETRY_BACKOFF_S)


async def _score_samples(samples: list[dict]) -> list[dict]:
    llm = _judge_llm()
    embeddings = HuggingFaceEmbeddings(model=EMBEDDING_MODEL, device="cpu")

    context_precision = ContextPrecisionWithReference(llm=llm)
    context_recall = ContextRecall(llm=llm)
    faithfulness = Faithfulness(llm=llm)
    answer_relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)

    scored = []
    for sample in samples:
        # A refusal on a scenario this dataset expects grounded (RAGAS_SCENARIOS
        # is built only from scenarios 1-7, all `expect_grounded: True`) is a
        # real quality failure, not a missing measurement — score it 0 across
        # every metric rather than asking ragas to judge it. Every metric's
        # own `.ascore()` requires a non-empty response AND a non-empty
        # retrieved_contexts list (confirmed directly: all four raise
        # `ValueError` on an empty one), so an empty-response sample cannot
        # be passed through the judge at all — there's nothing to submit an
        # empty answer against source text for. This is the tool-selection
        # instability Task Group 3 already measured (5-run average ~78%
        # pass), showing up here as an occasional forced 0 rather than a
        # crash.
        if not sample["response"] or not sample["retrieved_contexts"]:
            scored.append(
                {
                    "name": sample["name"],
                    "context_precision": 0.0,
                    "context_recall": 0.0,
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.0,
                    "refused": True,
                }
            )
            continue

        cp = await _judged(lambda: context_precision.ascore(
            user_input=sample["user_input"],
            reference=sample["reference"],
            retrieved_contexts=sample["retrieved_contexts"],
        ))
        cr = await _judged(lambda: context_recall.ascore(
            user_input=sample["user_input"],
            retrieved_contexts=sample["retrieved_contexts"],
            reference=sample["reference"],
        ))
        fa = await _judged(lambda: faithfulness.ascore(
            user_input=sample["user_input"],
            response=sample["response"],
            retrieved_contexts=sample["retrieved_contexts"],
        ))
        ar = await _judged(lambda: answer_relevancy.ascore(
            user_input=sample["user_input"],
            response=sample["response"],
        ))
        scored.append(
            {
                "name": sample["name"],
                "context_precision": cp.value,
                "context_recall": cr.value,
                "faithfulness": fa.value,
                "answer_relevancy": ar.value,
                "refused": False,
            }
        )
    return scored


_METRICS = ("context_precision", "context_recall", "faithfulness", "answer_relevancy")


def _average(scored: list[dict]) -> dict:
    return {metric: round(sum(s[metric] for s in scored) / len(scored), 4) for metric in _METRICS}


def measure(repeats: int = 1) -> list[dict]:
    """Records two averages per run, not one — a refused scenario scores
    0 on every metric by construction (`_score_samples`'s refusal
    handling), which measures the tool-selection instability Task Group
    3 already tracks separately, not answer quality. Averaging refusals
    in with answered scenarios makes both unmeasurable: a quality
    regression and a refusal-rate regression would move the same blended
    number for two different reasons, indistinguishably. `average_all`
    is recorded for visibility; `average_answered` (over only the
    scenarios that produced an answer) is what design.md's regression
    floors are actually set against. `refusal_rate` is recorded as its
    own figure rather than folded into either average — see design.md's
    "RAGAS baseline" decision for why its own threshold defers to Task
    Group 3's already-tracked stability history instead of being
    re-derived here from a single n=7 run.
    """
    db = SessionLocal()
    batch_id = datetime.now(timezone.utc).isoformat()
    entries = []
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        for i in range(repeats):
            t0 = time.perf_counter()
            samples = _run_agent_for_ragas(db)
            scored = asyncio.run(_score_samples(samples))
            answered = [s for s in scored if not s["refused"]]
            refusal_rate = round((len(scored) - len(answered)) / len(scored), 4)
            entry = {
                "batch_id": batch_id,
                "run": i,
                "per_scenario": scored,
                "average_all": _average(scored),
                "average_answered": _average(answered) if answered else None,
                "refusal_rate": refusal_rate,
                "duration_s": round(time.perf_counter() - t0, 1),
            }
            entries.append(entry)
            f.write(json.dumps(entry) + "\n")
            f.flush()
            print(
                f"run {i}: refusal_rate={refusal_rate} "
                f"average_answered={entry['average_answered']} "
                f"average_all={entry['average_all']}"
            )
    return entries


def main() -> None:
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    entries = measure(repeats)
    print(f"\nRecorded {len(entries)} run(s) to {HISTORY_PATH}")


if __name__ == "__main__":
    main()
