## 0. Baseline

- [x] 0.1 Confirm the dev stack is up (Docker Compose Postgres + Redis,
      `uvicorn --reload`) and run the full existing suite (137 tests
      collected) to confirm a clean pass before any change here.
      **137 passed, 0 failed, 944.22s.**
- [x] 0.2 Run `python -m app.rag.calibration`, transcribe all nine rows
      (query, expected, top score, top distance, top source) into
      design.md's calibration table's "Baseline" column.
- [x] 0.3 Record query-time embedding latency (average of 3 runs of a
      representative query) and available RAM with the dev stack running,
      in design.md.

## 1. LangGraph orchestration

- [x] 1.1 Add `langgraph` and `langgraph-checkpoint-postgres` to
      `requirements.txt`; install. **Also required `psycopg[binary]`
      (langgraph-checkpoint-postgres depends on psycopg v3, which has no
      pure-Python libpq wrapper on Windows without the binary extra) —
      added to requirements.txt alongside.**
- [x] 1.2 `api/app/graph/state.py`: define the graph's state shape (case
      id, message, pending facts, intent/extraction, agent conversation
      messages, tool trace, submitted answer, verification result).
      **Also added an explicit `next_step` routing field — `rag_answer:
      None` alone can't distinguish "still looping" from "terminally
      failed", so every agent/tools/verify node sets `next_step`
      explicitly and edges.py reads only that.**
- [x] 1.3 `api/app/graph/nodes.py`: four linear nodes (`classify`,
      `record_facts`, `next_question`, `resolve`), each a thin wrapper
      calling the existing `app.chat.classifier` / `app.engine.*`
      functions — no reimplementation. **`resolve` reuses `resolve_case`
      exactly as `app/api/cases.py` does today (age-first precedence,
      case.resolved_at commit); its dataclass result is serialized to a
      plain dict before entering state — never the raw `CaseResolution`
      object — so the checkpointer only ever persists JSON-safe data.**
- [x] 1.4 `api/app/graph/agent_nodes.py`: the tool-calling cycle —
      `agent` (one `client.messages.create` turn over `app.chat.tools.
      TOOL_SCHEMAS` + `submit_answer`), `tools` (executes whichever tool
      the model selected, via `app.chat.tools.call_tool`), `verify`
      (the submission-vs-tool-results check, adapted from `agent.py`'s
      `_verify_submission` and value-tracking logic — reused for its
      content, restructured out of the `while True` loop into graph
      form per design.md's revised decision). **Reuses `app.chat.
      agent`'s constants/schemas/helpers directly (import, not
      duplicate) — that module is untouched and still directly tested.
      Known simplification, documented in the module docstring: a model
      turn mixing a `submit_answer` with other tool calls only acts on
      the other tool calls that iteration; golden-parity testing (1.8)
      checks whether this ever actually diverges behavior.**
- [x] 1.5 `api/app/graph/edges.py`: deterministic Python conditional-edge
      functions — `agent → tools` on a tool-call turn, `tools → agent`
      looping back, `agent → verify` on a `submit_answer` call, `verify
      → agent` with an explanation on a failed check (one retry budget,
      matching `agent.py`'s `MAX_VERIFICATION_RETRIES`), `verify → END`
      on success or a second failure. `next_question` node still calls
      the existing `next_question.py` unchanged — the graph never lets
      model output select routing.
- [x] 1.6 `api/app/graph/checkpointer.py`: wire the LangGraph Postgres
      checkpointer, using its own setup/migration, not `app.models.Base`.
      **Verified live against the dev Postgres: `.setup()` created its
      own tables, separate from Alembic's chain.**
- [x] 1.7 `api/app/graph/build.py`: compile the `StateGraph` from the four
      linear nodes, the `agent`/`tools`/`verify` cycle, edges, and
      checkpointer. **Also added `run_message_turn`/`run_resolve_action`
      — the two entry-point functions `router.py` and `app/api/cases.py`
      call, translating graph state to/from the same `ChatOutcome`/
      resolution-dict shapes those callers already used, so 1.9's swap
      is a minimal diff. Thread id is freshly generated per turn (see
      build.py's module docstring) rather than reused per-case, so a
      turn's `agent_messages`/`tool_trace` never leak into the next
      turn via checkpoint resume.** Compiled and smoke-tested (no DB):
      all 7 nodes wire correctly with no warnings. Compiled and
      smoke-tested against the live dev Postgres: checkpointer `.setup()`
      succeeds.
- [x] 1.8 Golden-parity test (`tests/graph/test_golden_parity.py`): (a)
      every GOLDEN_SCENARIOS answer set seeded as real `CaseAnswer` rows,
      resolved via the graph's `resolve` action, compared against
      `resolve_case()` called directly; (b) one full renewal conversation
      (age/holds_passport/name_changed/dual_citizen/profession/
      buddhist_priest/district/service_basis, all deterministic tokens)
      driven through both the pre-graph `router.handle_message` and
      `run_message_turn` on separately seeded cases, recorded answers and
      resolved plans compared. **Reported and resolved per the "report
      any diff" instruction: scenario 9 ("Applying from abroad",
      `district=None`) initially failed — traced to a test-fixture
      mismatch, not a graph behavior difference (`resolve_case()` called
      directly with a raw dict treats `district: None` as "known to have
      no district"; the graph's `resolve` action goes through the real
      CASE_ANSWER-backed readiness gate — the same gate `app/api/
      cases.py` and `app/chat/tools.py` already enforce today — which has
      no way to represent "explicitly unknown", only "not yet answered",
      so it correctly reports not-ready). User decided: exclude scenario
      9 from this parity test with the reasoning documented inline, no
      production code change. **10/10 passing** (9 resolve-path
      scenarios + the message-path conversation test), 103s.
- [x] 1.9 Swapped `app/chat/router.py`'s `handle_message` to
      `app.graph.build.run_message_turn`; the pre-graph implementation is
      deleted (router.py is now a 15-line re-export module, per design.md's
      "shim only until parity, then delete" decision). **Also folded
      `app/api/cases.py`'s resolve route into the graph's `action="resolve"`
      path** (`run_resolve_action`), per design.md's "two entry paths
      sharing next_question" decision — added `CaseResolutionOut.
      from_resolution_dict` to build the same response directly from the
      graph's JSON-safe resolution dict. Rewrote `tests/chat/test_router.py`
      to mock at the new seams (`app.graph.nodes._classify`, the
      `anthropic.Anthropic` client `agent_node` uses) instead of the
      deleted `chat_router.classify`/`chat_router.answer_question`.
      **Two real bugs found and fixed during this task, both by running
      the actual suite, not by inspection:**
      (1) `agent_node` stored raw Anthropic SDK response objects directly
      into checkpointed state — not msgpack-serializable; fixed by
      converting every content block to a plain dict immediately after
      each model response.
      (2) `verify_node` called `.isoformat()` on `Citation.verified_at`,
      assuming it was always a real `datetime` per its dataclass type
      hint — `app.chat.agent._build_citations` (unmodified, pre-existing)
      actually assigns it from `retrieve_documents`'s already-ISO-string
      chunk dict, a pre-existing type-hint/reality mismatch in that
      function nothing had previously exercised at this exact boundary;
      fixed to accept either.
      **Full suite (147 tests: 137 original + `test_golden_parity.py`'s
      10) passes: 145 green + 2 flaky reruns green** — both flaky
      failures were the same complex "Should I amend my passport or get
      a new one?" comparison query; one (`test_agent.py`) calls
      `answer_with_agent` directly, never touching the graph at all,
      confirming it's pre-existing model-response variance (the same
      flakiness class 6.11's own completion notes already accept for
      real-API tests), not a regression — both passed cleanly on
      immediate retry.
- [x] 1.10 Export the graph visualization (e.g. Mermaid or PNG via
      LangGraph's built-in export) to a checked-in file for review.
      **`api/app/graph/export_visualization.py`, output at
      `api/app/graph/graph_visualization.mmd`** — clearly shows the
      4-node linear path, the two entry points sharing `next_question`,
      and the `agent ⇄ tools`/`agent ⇄ verify` cycle with its `→ end`
      exits.
- [x] 1.11 Unit test (`tests/graph/test_agent_cycle.py`): a mocked model
      response shaped like a routing instruction (JSON-looking text
      naming a node/"skip verification") does not change which node the
      graph transitions to next — the graph correctly treats it as plain
      no-tool-call text and falls back to the explicit no-relevant-match
      response, never parsing it as a directive.
- [x] 1.12 Unit test: the `agent → tools → agent` cycle handles more than
      one tool call in a single turn (two `get_fee` calls) before
      reaching `verify` — both execute, both land in the trace, then
      `submit_answer` verifies cleanly against both.
- [x] 1.13 Unit test: a failed `verify` retries `agent` once with an
      explanation, and a second consecutive failure ends the turn with
      the explicit no-relevant-match response, not a third attempt.
      **Test-harness bug found and fixed while writing this** (in both
      the new `tests/graph/conftest.py` fixture and the equivalent local
      helper in `tests/chat/test_router.py`): the fake Anthropic client
      was rebuilt fresh on every `agent_node` invocation, discarding
      response-consumption state between calls — invisible whenever a
      test's responses happened to be identical or single-call, but it
      silently broke multi-distinct-response scenarios (a 3rd tool-call
      round-trip nobody asked for, tripping `MAX_TOOL_ITERATIONS`).
      Fixed by building the fake client once per test and reusing the
      same instance across every `Anthropic()` call.
- [x] 1.14 Unit test: clearing/resetting a case's checkpointed
      conversation position (`get_checkpointer().delete_thread(...)`)
      does not lose or alter any `CASE_ANSWER` row.
- [x] 1.15 Full regression: all pre-existing tests (137) plus 1.8/1.11/
      1.12/1.13/1.14 pass. **151 total (137 original + 14 new across
      `tests/graph/`): 150 green, 1 flaky
      (`test_agent.py::test_amend_vs_renew_produces_a_multi_step_trace_with_both_fees`
      — the same complex comparison query flaky for the third time this
      session, never touching the graph), confirmed green on immediate
      retry (53.99s).**
- [x] 1.16 **Measure**: re-run `python -m app.rag.calibration`; confirm
      unchanged from baseline (the graph migration touches orchestration,
      not retrieval) — record in design.md as a sanity check row, not a
      new column, since no retrieval-facing change happened this step.
      **Confirmed: every score/distance identical to baseline, to the
      digit, across all nine queries.**

## 2. Reranker

- [x] 2.1 Add `bge-reranker-base` (self-hosted, CPU) as a dependency;
      `api/app/rag/rerank.py`: `rerank(query, candidates) -> list[Scored]`
      loading the model once (`lru_cache`, matching `embedding.py`'s
      pattern). **No new pip package needed — `CrossEncoder` is already
      part of the installed `sentence-transformers`; only the model
      weights (via HF Hub) are new.**
- [x] 2.2 Wire into `app/rag/retrieval.py`: hybrid search's candidate
      pool widened to 20 (already `_CANDIDATE_POOL_SIZE`), reranker
      scores all 20, top 5 selected for generation. (No separate graph
      nodes — reranking lives inside `retrieve_documents`'s own
      implementation, per graph-orchestration's revised node list from
      Task Group 1: "Reranking is not a separate top-level graph node.")
- [x] 2.3 Recalibrate the weak-match threshold — **materially revised
      from the original plan after measurement, not a simple threshold
      pick.** Investigation history (fully recorded in design.md):
      (1) a pure reranker-score threshold cannot separate the
      calibration set at all — "visa to Australia" (reject) scored
      0.973-0.999, higher than 5 of 6 accept queries, confirmed to be a
      property of `bge-reranker-base` itself (lexical overlap on "apply
      /application" phrasing), not a scoring bug;
      (2) investigating that false-accept first surfaced and led to
      fixing a real, pre-existing chunking defect (5 bare-question
      chunks on `pages_e.php?id=8`, unrelated to this branch's original
      scope but found and fixed along the way — see Task Group 2's
      chunking-fix subtasks below) — kept regardless, but it didn't
      resolve the false-accept (which got worse, not better);
      (3) resolved by requiring the pre-rerank hybrid signal to agree
      with the reranker score (AND, not a replacement) — but naively
      gating on the *reranked* top-1's own hybrid score broke two
      genuine accept queries (reranking had correctly promoted a
      different chunk than hybrid's own top pick, and that chunk's
      individual hybrid score alone read weak); fixed by evaluating the
      hybrid gate against the hybrid pool's own top-1, once, at the
      query level, independent of which chunk reranking later promotes.
      **Final: 9/9 correct**, verified both via
      `calibration.py::measure_reranked` and directly against
      `retrieve()`.
- [x] 2.3a **(Discovered, not originally scoped) Chunking defect fix:**
      `app/ingestion/chunking.py::build_chunks` — a prose run under
      `_MIN_STANDALONE_PROSE_WORDS` (12) immediately preceding a
      table/list block is now merged into that block instead of emitted
      as its own near-content-free chunk (falls back to standalone only
      at a document's end, so nothing is silently dropped). Re-ran
      `python -m app.ingestion.rechunk` against all 8 approved documents
      — `pages_e.php?id=8` went from 40 to 35 chunks, all 5 defective
      fragments confirmed merged. `document-chunking` spec delta updated
      (MODIFIED "A document's text is split into passage-sized chunks").
- [x] 2.4 Unit tests (`tests/rag/test_rerank.py`): reranking narrows a
      candidate pool to the top-k, best-score-first; the weak-match
      check requires the reranker score's own threshold (not raw
      cosine/RRF alone) AND the pre-rerank hybrid signal — three cases
      covering "hybrid ok, rerank weak → reject", "rerank strong, hybrid
      not ok → reject", "both agree → accept".
- [x] 2.5 Full regression: all pre-existing tests pass, plus 2.4.
      **151/151 pass** (one legitimately outdated assertion in
      `tests/rag/test_retrieval.py::test_strong_match_returns_relevant_result`
      updated — it asserted the returned top chunk's raw
      `vector_distance`, which reranking can now legitimately promote a
      different, better chunk past; two other failures during this
      step's runs were one-off live-model variance, confirmed clean on
      immediate retry, unrelated to this step's code).
- [x] 2.6 **Measure**: re-run calibration; record "After Step 2" column
      in design.md. Record available RAM with the reranker loaded
      (dev stack + reranker resident, no bge-base yet). **9/9 correct.
      RAM: ~8.47GB free of ~20.16GB installed with both embedding and
      reranker models resident — comfortable headroom.**
- [x] 2.7 Record query-time latency with reranking added, alongside the
      baseline latency, in design.md. **12,928ms average (3 runs) with
      `bge-reranker-base`, versus 18.78ms baseline — a ~700x increase,
      flagged as unacceptable UX rather than silently absorbed. User
      directive followed in order:**
- [x] 2.8 **Model swap** (per explicit user direction after 2.7's
      finding): `BAAI/bge-reranker-base` (278M params) →
      `cross-encoder/ms-marco-MiniLM-L-6-v2` (~22M params). Recalibrated
      from scratch — different score scale entirely (raw unbounded
      logits, not [0,1] sigmoid). `_RERANK_THRESHOLD` reset to -5.0 (the
      smaller model scores one genuine accept query, "working hours at
      the Head Office," far worse than the others — -2.943, a real
      accuracy cost of the lighter model). **9/9 still correct.
      Latency: 2,233ms average — down from 12,928ms (~5.8x faster), but
      still above the 1.5s target; reported as measured, not rounded up
      to "close enough."**
- [x] 2.9 **Is reranking worth shipping? Measured, not assumed** (per
      explicit user direction): compared the full calibration set with
      reranking disabled (hybrid alone) against hybrid+small-reranker
      (AND-gated). Both score 9/9 — reranking changes **zero**
      accept/reject outcomes on this calibration set, because hybrid
      search alone already resolved every one of the 9 queries correctly
      before reranking existed (Phase 6.7) and still does; the AND-gate
      means every reject query already fails on the hybrid signal alone,
      so the reranker score never gets to override anything. Reranking's
      only measured effect is reordering which chunk reaches generation
      for an already-correctly-accepted query (confirmed for 2 of the 6
      accept queries) — a real effect, but not one this accept/reject
      harness measures (that needs RAGAS, Step 7, not yet built).
      **Recommendation followed: reranking ships disabled by default.**
      `RERANK_ENABLED` config flag added (`RAG_RERANK_ENABLED=true` to
      re-enable) — code stays in place behind the flag for revisiting on
      better hardware or once RAGAS can measure generation-quality
      effects, per the user's explicit instruction. `retrieval-
      reranking` spec delta updated to describe the flag-gated,
      default-off behavior and the measured-decision requirement.
      Full decision record (margins, both configurations' numbers) in
      design.md.
- [x] 2.10 Full regression with the final configuration (reranking
      disabled by default): **155/155 pass** (137 original + 18 new
      across this step's test files). Also verified explicitly with
      `RAG_RERANK_ENABLED=true`: all 16 `tests/rag/` tests still pass
      with reranking forced on.

## 3. Golden set growth (moved ahead of the embedding upgrade — see design.md's "Reordering" decision)

- [x] 3.1 **Designed to discriminate, not to pass** (per explicit user
      instruction) — two harnesses, since renewal-branch scenarios and
      open-question scenarios need genuinely different mechanisms
      (`resolve_case()` vs. the live agent), not one shared pattern:
      - **10 new renewal-branch scenarios**
        (`tests/engine/golden_scenarios.py`, total now 20) — found by
        reading `app/seed/phase4_renewal.py`'s actual condition links,
        not guessed: the under-16 scope gate (never tested before), both
        edges of the fingerprint requirement's 16-60 age range, an
        AND-of-two-conditions requirement's positive case *and* its
        near-miss (section 19(2) alone must NOT trigger it), the
        profession-stated branch, a dual-citizen+buddhist-priest
        interaction that could plausibly double-add a requirement if the
        resolver's set-replacement had a bug, and a combined
        boundary-age+dual-citizen+section-19(2)+urgent stress case.
      - **10 new open-question scenarios**
        (`tests/graph/golden_open_questions.py` +
        `test_golden_open_questions.py`, run for real against
        `answer_with_agent`, no mocking) — hard paraphrases far from
        source wording, multi-tool questions (fee+office,
        amend-vs-renew), exact-identifier queries (NMRP, a circular
        number, an alteration fee) verified directly against real
        `DOCUMENT_CHUNK` content first (not guessed), near-miss
        out-of-corpus queries adjacent to real topics (driving license
        at a real office; dual citizenship from India), an explicit
        out-of-scope refusal (online submission), and one scenario
        (age-tiered urgent fee for a minor) deliberately targeting a
        real system gap: `get_fee`'s tool schema has no age parameter,
        so it cannot distinguish the corpus's separate below-16 fee
        table from the adult one.
      - **Total: 30 scenarios** (20 + 10), within the spec's 25-30 band.
- [x] 3.2 Full regression — **reported honestly, not adjusted to pass**:
      - Renewal-branch set: **20/20** (rules-engine correctness is
        safety-critical — "a wrong checklist is worse than no
        checklist" per CLAUDE.md — so 100% here is the right outcome,
        not evidence the set was too easy; every scenario was
        independently derived from the seed data's actual condition
        logic, not from the engine's own output).
      - Open-question set: **first run showed 6/10, contaminated by the
        Anthropic account's API credit balance running out mid-run**
        (hundreds of live calls across this session) — caught by
        investigating rather than reporting the number as-is: a bare
        `client.messages.create()` call reproduced the exact
        `BadRequestError`, explaining why `answer_with_agent`'s existing
        `except Exception: return None` fallback made 4 real failures
        indistinguishable from 3 correct refusals. **After the user
        added credits, a clean re-run: 7/10.** One of the three
        failures (the NMRP exact-identifier query) was manually
        re-traced afterward and — on that separate call — retrieved the
        correct passage and submitted a well-grounded, correctly-cited
        answer; the same query failed in the actual parametrized run.
        This means the underlying capability exists but the model's
        decision to invoke `retrieve_documents` on this exact query is
        not reliable run to run — a real, reportable finding in its own
        right (a discriminating query, not a broken one), left as a
        genuine test failure rather than re-run until it passes.
      - **Combined: 27/30** on the dedicated clean re-run. A subsequent
        full-suite run (unrelated to this task — routine regression)
        showed the open-question set at 6/10 that time, with a
        *different* subset failing than either of the two dedicated
        runs (1, 2, 4, 6, 7 that time vs. 1, 2, 4 on the clean dedicated
        run vs. 4, 5, 6, 7 on the credit-contaminated run). This is
        reported as further evidence the set is genuinely discriminating
        — real run-to-run model variance on deliberately hard queries —
        not chased toward a single "final" number. No fixed pass rate is
        claimed as canonical; **27/30 (dedicated, credit-clean run)** is
        the number recorded as this task's baseline measurement, with
        the variance itself noted as a property of the current system,
        not of the measurement.
- [x] 3.3 **Tool-selection instability fix** (per explicit user
      instruction, before proceeding to RAGAS — an unstable system
      cannot support attributable RAGAS comparisons). Investigated and
      fixed four distinct real bugs, not one:
      1. **Forced first-turn tool call.** `agent_node`/`answer_with_agent`
         previously only *nudged* the model to try a tool before giving
         up; the model could still ignore the nudge and refuse outright
         with zero tool calls — confirmed directly: the exact same query
         sometimes retrieved and grounded correctly, sometimes refused
         with no tool call at all, run to run. Fixed by passing
         `tool_choice={"type": "any"}` with a submit_answer-excluded
         tool list on the first turn only — the model structurally
         cannot decline without having tried something. The original
         nudge logic is now unreachable on turn 0, left in place only as
         a defensive fallback for a later turn.
      2. **Case-scoped tool misfire with no case.** The forced-any fix
         alone had a side effect: with no `case_id`, a model forced to
         call *something* sometimes grabbed a case-scoped tool
         (`get_next_question`) with a placeholder id instead of the
         obviously relevant `get_fee`/`retrieve_documents` — wasting an
         iteration on a call that could only fail. Fixed by restricting
         the forced first-turn tool list to case-independent tools
         (`retrieve_documents`, `get_fee`, `find_office`) whenever no
         case_id is present.
      3. **False-positive verification rejection on a cited chunk's own
         fee mention.** The deeper, more consequential bug: a
         correctly-retrieved, correctly-cited chunk's own text stated a
         fee/fine amount (e.g. "a fine of Rs. 20,000"); the model
         reported it in `fee_values_used` per the *original* system
         prompt's literal instruction ("every fee amount your answer
         states"); `_verify_submission` only ever checked
         `fee_values_used` against `get_fee`/`resolve_case`/
         `compare_amendment_vs_renewal` results, never against cited
         chunk text — so a fully-grounded answer was rejected as if the
         model had invented the number. Fixed two ways: (a) narrowed the
         system prompt and schema descriptions so `fee_values_used`/
         `office_names_used` are explicitly only for tool-computed
         values, never a value merely mentioned in cited text (already
         covered by `chunk_citations`); (b) added a structural backstop
         to `_verify_submission` (`_value_appears_in_cited_chunk_text`)
         that also accepts a fee value if it appears verbatim within a
         chunk the submission actually cited — not relying on prompt
         compliance alone for a check that exists to protect against
         hallucination, not against citing real cited text.
      4. **Chunk-citations sometimes left empty despite using retrieved
         content.** A related, still only partially resolved case: the
         model sometimes states a fact clearly drawn from a retrieved
         chunk (a caveat, a legacy amount) while submitting
         `chunk_citations: null`/empty, tripping the (correct)
         "retrieved chunks but cited none" check — and, observed
         directly, sometimes repeats the identical mistake on the one
         verification retry, exhausting the budget. Strengthened the
         system prompt to state explicitly that any fact used from
         retrieved results — even in passing — must be cited, and that
         empty citations are only correct when retrieval's results
         contributed nothing at all. This measurably reduced but did not
         fully eliminate the failure (see 3.4's numbers) — a genuine
         residual model-reliability limit, reported honestly rather than
         engineered away with a further structural workaround within
         this task's scope.
      A fifth attempted fix — `temperature=0`, to reduce run-to-run
      sampling variance — was tried and immediately reverted: this
      model generation returns `400 temperature is deprecated for this
      model` for any non-default value. Confirmed directly, not assumed;
      removed entirely from both `agent.py` and `agent_nodes.py`.
      Also fixed in this task, per explicit user instruction:
      **`get_fee`'s missing age parameter** — the corpus's below-16 fee
      tier (LKR 3,000/9,000) existed only in source-page text, never as
      seeded structured data, so `get_fee` could never return it
      regardless of what the model asked. Added `FeeRule.condition_id`-
      linked below-16 fee rules (reusing the existing age Condition,
      not a new column), `resolve_fee(..., age=...)`, `get_fee`'s new
      optional `age` parameter, and a system-prompt note to pass it when
      relevant. Verified directly at both boundaries (age 15 → child
      tier, age 16 → adult tier) and via new unit tests
      (`tests/engine/test_fees.py`).
- [x] 3.4 **Re-ran the open-question set five times** (post-fix, the
      code state that stands — not the reverted temperature=0 attempt):
      **8/10, 7/10, 7/10, 8/10, 9/10.** Compared against the pre-fix
      baseline (6-7/10, with a *different* subset of scenarios failing
      almost every run): a real, substantial improvement — average pass
      rate rose from ~65% to ~78%, and the failing set converged from
      "up to 5 different scenarios, largely unpredictable" to
      consistently scenarios 1, 2, and 6 (with 1 and 6 eventually
      passing too, on run 5). **Not the full run-to-run determinism the
      user asked for** — reported as such, not rounded up. The
      remaining variance traces to bug #4 above (citation omission not
      fully eliminated by prompt strengthening) and ordinary live-model
      sampling variance this model doesn't allow disabling
      (`temperature` unsupported). Two Anthropic API credit exhaustions
      occurred during this task's investigation (this branch's own
      cumulative live-API volume) — both caught by reproducing the exact
      `BadRequestError` before reporting any number, per this project's
      now-established practice for this failure mode (see design.md's
      Risk entry, first recorded during Task 3.2).
- [x] 3.3a **Tracked the stability metric instead of measuring it once**
      (per explicit user instruction): refactored the per-scenario
      pass/fail logic out of `test_golden_open_questions.py` into a
      shared `golden_open_question_eval.py::evaluate_scenario`, so the
      per-commit regression gate and the tracked measurement can never
      drift apart on what "pass" means. Added
      `measure_open_question_stability.py` (run with `python -m
      tests.graph.measure_open_question_stability [N]`, default 5) —
      appends one JSON line per individual run to the git-tracked
      `stability_history.jsonl`, so a trend is visible over time rather
      than re-discovered by chance. Added
      `test_stability_history.py::test_latest_stability_batch_average_
      has_not_regressed` — reads the latest recorded batch and asserts
      its *average* pass rate (not every individual run) hasn't dropped
      below a floor with margin under what was observed; checking the
      average rather than a per-run floor was a deliberate choice, not
      an oversight — the very first tracked batch already contained one
      run at 5/9 (55.6%) alongside four at 6-8/9, so gating on the
      single worst run in a batch would false-alarm on ordinary noise
      this metric is known to have. This test doesn't itself re-run the
      5x measurement (5x the live-API cost of the normal per-commit
      gate) — it only checks what's already recorded, so re-running the
      script periodically (or after a change plausibly affecting the
      agent's tool-use reliability) is what keeps the tracked history
      current.
- [x] 3.3b **Seeded real tracked history** by running the actual script
      (not backfilled/fabricated): **8/9, 5/9, 8/9, 8/9, 6/9** — average
      **77.8%** (35/45). Denominator is 9, not 10: scenario 9 (the
      genuinely ambiguous dual-citizenship-from-India case) is correctly
      excluded as "skipped," not asserted — this is a more precise
      accounting than the earlier manual "X/10" figures, which
      inconsistently included it. This run also surfaced two failure
      modes not seen in the five manual runs that preceded it (scenario
      3's exact-identifier query, and scenario 8's near-miss refusal,
      each failing once) — confirming the residual variance is broader
      than "scenarios 1/2/6 specifically," a more honest picture than
      the manual runs alone suggested. Scenario 1 (the hard paraphrase)
      failed 4 of 5 tracked runs — the single most persistent residual
      failure, consistent with bug #4 in 3.3 (citation-omission on
      content used only in passing) being only partially resolved by
      the prompt strengthening.
- [x] 3.6 **Confirmed, directly, not assumed** (per explicit user
      instruction): the below-16 fee tier is genuinely seeded as
      structured `FeeRule` data — all 4 renewal fee rules queried
      directly from the live database show the 2 below-16 rows
      correctly linked via `condition_id` to `age lessThan 16` and
      citing `pages_e.php?id=8`, the same source as the adult tier. The
      under-16 scope gate still fires correctly and unconditionally: a
      direct `resolve_case()` call with `age=10` (urgent) returns
      `scope_gate` set, `requirements=[]`, `fee=None`, `offices=None` —
      confirming the new `FeeRule` rows cannot be reached by a real
      citizen case (the scope gate short-circuits in `resolver.py`
      before fee resolution runs at all, entirely unaffected by
      `fees.py`/`tools.py`'s changes). The scope gate's own existing
      message text already named "LKR 3,000/9,000" before this fix —
      confirming the seeded amounts match a fact the codebase already
      documented, not a guessed number.
- [x] 3.5 Full regression after all of Task 3.3's fixes: **201 passed, 5
      failed, 2 skipped** (611.82s). All 5 failures individually
      re-isolated and retried clean (`test_name_change_message_
      acknowledges_marriage_certificate_and_skips_question`,
      `test_grounded_answer_returns_citations`,
      `test_amend_vs_renew_tool_trace_is_persisted_and_retrievable`,
      open-question scenario 1, and the established `test_agent.py`
      amend-vs-renew test) — all live-model variance, the same class
      this project's real-API tests already accept, not a regression
      from this task's changes. The fee-verification structural
      backstop was specifically checked against the existing
      `test_verify_submission_*` unit tests (still correctly reject a
      genuinely fabricated, uncited fee) to confirm it only widens
      grounding for cited text, not verification generally. Two
      Anthropic API credit exhaustions during this task (this branch's
      cumulative live-API volume across Task Groups 1-3) — both caught
      and reported before any number, both resolved by the user adding
      credits.

## 4. RAGAS (moved ahead of the embedding upgrade)

- [x] 4.0 **Cost-engineering pivot** (user instruction, mid-Step-4: fixed
      student-project budget, no more Claude credits available — free
      tiers wherever the output is not citizen-facing, paid inference
      reserved for `app.chat.agent` alone). Pulled Step 10's LiteLLM
      gateway forward and implemented first:
  - [x] 4.0.1 `app/llm/gateway.py`: `structured_completion(job, system,
        user, response_model, max_tokens)` over `litellm.completion`,
        model per job config-driven via `LLM_MODEL_<JOB>` env vars,
        defaulting to Gemini's free tier. `app.chat.agent` deliberately
        not routed through it (Anthropic-native tool-calling, no
        equivalent shape here; see design.md).
  - [x] 4.0.2 `app.chat.classifier`, `app.chat.rephrase` moved to
        Gemini's free tier through the gateway; `app.chat.acknowledge`
        moved too (not one of the three explicitly-named jobs, same
        profile, flagged for confirmation). Existing fallback paths
        (canonical prompt, `None`, forced `intent="question"`) now also
        cover a Gemini call failure, not just a low-confidence Claude
        result.
  - [x] 4.0.3 `app.ingestion.pdf_extraction`: free three-stage chain
        (Tesseract via `pytesseract`/PyMuPDF, then Gemini Flash vision)
        ahead of the existing Claude OCR path, which becomes a
        `PDF_OCR_CLAUDE_LAST_RESORT_ENABLED`-gated last resort. Verified
        against `instructions_english_td.pdf` via
        `tests/ingestion/test_pdf_extraction_chain.py`, bypassing the
        extraction cache so the existing cached result is untouched:
        Tesseract alone produced 8,522 characters (vs. 8,867 from the
        cached Claude extraction) with section (a) intact — the free
        chain never needed to fall through to Gemini vision for this
        document. Discovered and fixed a real chunking defect while
        chunking is unrelated — not touched here.
  - [x] 4.0.4 `pytest.ini` + `tests/conftest.py`: `real_api` marker,
        `addopts = -m "not real_api"`, and a `pytest_terminal_summary`
        hook reporting the skipped count on every default run. Every
        real-API test file/function identified individually and marked
        (not pattern-matched); two tests that mocked `anthropic.
        Anthropic` at the classifier/rephrase boundary updated to mock
        `app.llm.gateway.structured_completion` instead. Full suite
        confirmed green with zero external calls: 174 passed, 2
        (pre-existing, unrelated) skipped, 34 deselected.
  - [x] 4.0.5 CLAUDE.md's "How the Claude API is used" rewritten to "How
        the LLM APIs are used" — actual provider stated per job, agent
        named explicitly as the one job kept on Claude and why.
        design.md records the decision and the measured/structural
        before-after cost claim (token-count logging per job doesn't
        exist yet, so an exact dollar figure isn't asserted — the
        structural claim, that 4 of 6 jobs dropped from paid-every-turn
        to free-every-turn, is directly verifiable from the code).
- [x] 4.1 Add `ragas` as a dev/CI dependency.
- [x] 4.2 `api/tests/eval/ragas_baseline.py`: compute context precision,
      context recall, faithfulness, and answer relevancy against the
      grown golden set (Group 3); record the baseline scores in
      design.md. This baseline is measured with reranking at its shipped
      default (disabled) and with `all-MiniLM-L6-v2` (the embedding
      migration hasn't happened yet) — the reference point Group 5 (the
      embedding upgrade) and reranker re-evaluation below both compare
      against. Judge is Gemini's free tier per the cost-engineering
      pivot (4.0), not Claude — recorded as such in design.md.
- [x] 4.3 Resolve design.md's open question: set a concrete regression
      threshold per metric from the recorded baseline.
- [x] 4.4 ~~Re-evaluate the reranker against RAGAS~~ — **skipped, per
      explicit user instruction.** The reranker was already measured
      (Task Group 2) to add zero accept/reject margin over hybrid
      retrieval alone (9/9 on the calibration set both ways). RAGAS at
      this baseline's noise level (n=7, single run, faithfulness already
      varying 0.0-1.0 across answered scenarios) cannot resolve the
      reordering effect reranking does have — spending another ~7 paid
      Claude agent calls plus ~28 Gemini judge calls to measure an
      effect the instrument can't resolve isn't worth it. Reranking
      stays shipped-disabled behind `RAG_RERANK_ENABLED` (default
      `false`), unchanged. See design.md's "Task 4.4 — skipped"
      decision.
- [ ] 4.5 Wire the RAGAS run into the eventual CI pipeline (Step 9) as a
      recorded-but-non-blocking step for score drift, with the golden
      scenario pass/fail (deterministic) as the actual blocking gate,
      per design.md's decision.

## 5. Embedding upgrade (conditional on the memory gate; evaluated via RAGAS, not the calibration harness alone)

- [x] 5.1 **Memory gate measurement** — measured against the shipped
      configuration (reranking disabled, per user instruction), not
      against the reranker: shipped default (embedding model only)
      ~8.21GB free of ~20.16GB; + reranker also loaded (for reference)
      ~8.20GB (negligible addition); shipped embedding model +
      `bge-base-en-v1.5` candidate both loaded ~8.33GB. **Gate passes
      comfortably** — all three numbers land within measurement noise of
      each other; RAM is not close to a binding constraint on this
      machine, contrary to BACKEND_PLAN.md's original "~4GB often
      available" assumption. Full table in design.md.
- [ ] 5.2 Given the gate passes: Alembic migration altering
      `DOCUMENT_CHUNK.embedding` to `vector(768)`; write and run a
      rollback script (`vector(384)` + re-embed with MiniLM) so the
      migration is reversible per design.md's Migration Plan.
- [ ] 5.3 `app/ingestion/embedding.py`: swap `MODEL_NAME` to
      `bge-base-en-v1.5`.
- [ ] 5.4 Re-embed every chunk in the corpus; verify by count (chunks
      re-embedded == chunks in corpus) before proceeding.
- [ ] 5.5 Explicit verification: assert the same model name/version is
      used for both the re-embedding script and `app/rag/retrieval.py`'s
      query-time `embed_text` call (the "same model at ingestion and
      query time" requirement) — a test, not just a code review note.
- [ ] 5.6 Recalibrate the weak-match threshold again (768-dim changes
      the cosine-distance scale).
- [ ] 5.7 Full regression: all pre-existing tests pass.
- [ ] 5.8 **Measure — both instruments, not just the calibration
      harness**: re-run `python -m app.rag.calibration`; record "After
      Step 5" column (expected: still 9/9 — the calibration set is
      already saturated, per design.md's reordering rationale, so this
      is a regression check, not evidence of improvement). Re-run the
      RAGAS suite (Group 4) with the new embeddings and compare
      `average_answered` (not `average_all`) against 4.2's baseline —
      **this is the actual evidence for whether the upgrade helped**,
      not the calibration harness, and comparing the blended figure
      would let a `refusal_rate` change (unrelated to embeddings) move
      the number being read as evidence. Record query-time embedding
      latency before/after this step.

## 6. Docling evaluation

**Note (4.0):** "current path" below means, for the 3 PDFs already
cached, still literally Claude-vision (`.extraction.json`, untouched by
the free chain per design.md) — that comparison point hasn't moved. For
any PDF ingested for the first time after 4.0, the current default path
is the free three-stage chain (Tesseract, then Gemini vision), with
Claude only as a last resort — Docling would be compared against
whichever of those actually produced that document's text, not assumed
to be Claude.

- [ ] 6.1 `api/app/ingestion/docling_eval.py` (standalone script, not
      wired into the pipeline): run Docling against all three corpus
      PDFs.
- [ ] 6.2 Per PDF, record: character count, whether table structure is
      preserved, extraction time, and content present in one method but
      missing from the other (Docling vs. current pdfplumber/Claude-
      vision pipeline — see the 4.0 note above on what "current" means
      per PDF).
- [ ] 6.3 Specifically verify `instructions_english_td.pdf`: confirm
      whether Docling recovers the 21 form-filling instructions (section
      (a)) the current Claude-vision path already extracts (8,867
      characters) — also compare against the free chain's own result on
      this document, already measured in 4.0.3: Tesseract alone produced
      8,522 characters with section (a) intact, so Docling has two
      reference points here, not one — this is the one PDF where a
      regression would lose
      content that exists nowhere else in the corpus.
- [ ] 6.4 Write the full comparison into design.md's Decisions section
      (a table per PDF), regardless of outcome.
- [ ] 6.5 For any PDF where Docling measurably wins (per design.md's
      "measurably wins" criterion — more preserved structure, no lost
      content, comparable or better extraction time): switch that PDF's
      path in `app/ingestion/pdf_extraction.py`, re-extract, re-chunk,
      re-embed just that document.
- [ ] 6.6 If 6.5 ran for any document: verify the form-filling
      instructions (or equivalent unique content for other PDFs) remain
      retrievable via a targeted retrieval test.
- [ ] 6.7 Full regression: all pre-existing tests pass.

## 7. Langfuse

- [x] 7.1 Add a self-hosted Langfuse service to `docker-compose.yml`.
      (Two bugs fixed while resuming this after a disk-full incident:
      `langfuse-env` was missing `CLICKHOUSE_MIGRATION_URL` — web
      crash-looped; and without `CLICKHOUSE_CLUSTER_ENABLED: "false"`,
      migrations default to `ReplicatedMergeTree`/`ON CLUSTER default`,
      which fails with "no Zookeeper configuration" on this single-node
      ClickHouse. Also added a `langfuse-minio-init` one-shot service —
      the `langfuse` S3 bucket LANGFUSE_S3_EVENT_UPLOAD_BUCKET expects is
      never created by minio/web/worker themselves, so every event
      upload silently failed with `NoSuchBucket` until this was added.)
- [x] 7.2 Instrument every LLM API call — **not just Claude anymore**:
      per the cost-engineering pivot (4.0), classifier/rephrase/
      acknowledge now run on Gemini via `app.llm.gateway`, only the
      agent (and legacy, non-live `generation`) still call Claude
      directly. Trace every call regardless of provider, tagged with
      which one served it — a Langfuse view that only shows Claude calls
      would miss most of what actually runs on every turn now.
      (`app.llm.gateway.structured_completion` wraps the shared Gemini
      call site; `app.chat.agent` wraps `client.messages.create`.)
- [x] 7.3 Instrument every tool call (the six `app/chat/tools.py`
      wrappers) with Langfuse tracing. (`traced_tool` in `app.chat.agent`
      and `app.graph.agent_nodes`.)
- [x] 7.4 Instrument every graph node transition (Task Group 1's graph)
      with Langfuse tracing. (`@traced_node` on every node in
      `app.graph.nodes` and `app.graph.agent_nodes`.)
- [x] 7.5 Attach `case_id` to every trace so a case's traces are
      retrievable together. (`case_id` propagated as the Langfuse
      `session_id` via `turn_trace`/`traced_node`.)
- [x] 7.6 Integration test/manual check: a full conversation produces a
      Langfuse trace showing every graph transition and tool call for
      that conversation, retrievable by `case_id`. Verified by running a
      real message through `app.graph.build.run_message_turn` (the
      actual `app.chat.router` production path) and querying
      `/api/public/v2/observations` for the resulting `case_id`:
      `node:classify`, `node:record_facts`, `node:next_question`,
      `node:agent`, `node:tools`, a `get_next_question` tool call, and
      generations from both providers (`gateway:classify` on Gemini,
      `agent_turn`/`agent_turn_0` on Claude) all appeared under one
      session.
- [x] 7.7 Full regression: all pre-existing tests pass (tracing must be
      a non-blocking side effect — a tracing failure must not break the
      turn). 174 passed, 2 skipped (pre-existing), 34 deselected
      (`real_api` marker, per `pytest.ini`'s default), 0 failed.

## 8. Promptfoo

- [ ] 8.1 Add Promptfoo (Node-based) config for the classifier prompt —
      **now a Gemini prompt** (4.0): Promptfoo supports Gemini as a
      first-class provider, so this isn't blocked, but the config must
      target `gemini-flash-lite-latest` (or whatever `LLM_MODEL_CLASSIFY`
      currently resolves to), not Claude. Representative inputs and
      expected intent/extraction/contains_question outputs.
- [ ] 8.2 Promptfoo config for the agent prompt: representative inputs
      and expected tool-selection behavior. Unaffected by 4.0 — the
      agent is still Claude.
- [ ] 8.3 Promptfoo config for the rephrasing prompt — **now a Gemini
      prompt** (4.0), same provider-target correction as 8.1. Representative
      inputs and expected attribute-matching behavior.
- [ ] 8.4 Verify all three suites run locally and pass against the
      current prompts.

## 9. GitHub Actions

- [ ] 9.1 `.github/workflows/ci.yml`: Postgres 16 + pgvector and Redis 7
      as service containers.
- [x] 9.2 ~~Run pytest (137+ tests); external-API tests marked (e.g.
      `@pytest.mark.external_api`) and skipped in CI, with the skip
      count/list reported in the run's output.~~ **Done ahead of CI, as
      part of 4.0**: the marker is `@pytest.mark.real_api` (not
      `external_api` — align the CI workflow's `-m` flag to the actual
      name), registered in `pytest.ini` with `addopts = -m "not
      real_api"`, and `tests/conftest.py::pytest_terminal_summary`
      reports the skipped count on every run already. What's left for
      Task Group 9 is just running this existing suite inside the
      GitHub Actions workflow — the marker infrastructure itself doesn't
      need building there.
- [ ] 9.3 Run the golden scenario suite (Group 3) as a blocking gate —
      failure fails the build.
- [ ] 9.4 Run RAGAS (Group 4) as a recorded, non-blocking step per
      design.md's decision — gate (if ever made blocking) against
      `average_answered`, not `average_all`; log `refusal_rate`
      alongside it for visibility, cross-checked against Task Group 3's
      stability-history gate rather than given its own.
- [ ] 9.5 Run Promptfoo (Group 8) as a blocking gate on prompt regression.
- [ ] 9.6 Confirm a deliberately broken golden scenario (temporary local
      test) causes the workflow to fail, then revert the deliberate
      break.

## 10. After Steps 1–9 pass

- [ ] 10.1 Replace `pip`/`requirements.txt` workflow with `uv`; verify
      the dev setup (Docker Compose + `uv sync` + `uvicorn`) still
      reaches a passing `pytest` run.
- [x] 10.2 ~~Add a LiteLLM gateway in front of Claude API calls~~ —
      **superseded, done as part of 4.0.** Pulled forward and
      implemented ahead of RAGAS, not after Step 9, per the mid-branch
      cost-engineering pivot — `app/llm/gateway.py` exists and routes
      classify/rephrase/acknowledge. One correction to this task's
      original framing: it does not sit "in front of Claude API calls" —
      by design it fronts the non-agent jobs, which now run on Gemini,
      and `app.chat.agent` deliberately stays a direct Anthropic call
      outside the gateway (see design.md's "Cost-engineering pivot"
      decision for why). CLAUDE.md's job-boundary count is unchanged at
      six; only the provider per job changed, which CLAUDE.md's
      rewritten "How the LLM APIs are used" section now states
      explicitly.
- [ ] 10.3 `api/app/api/admin.py`: JWT auth dependency checking
      `ADMIN_USER.role in {reviewer, approver}`.
- [ ] 10.4 CRUD routes for requirements, conditions, fees, and offices,
      each behind the JWT dependency.
- [ ] 10.5 Tests: an unauthenticated edit request is rejected with no
      edit performed; an authenticated reviewer/approver request
      succeeds; all four entity types have working create/update/delete.
- [ ] 10.6 Full regression: all tests (137 + golden + Promptfoo-covered
      behavior) pass.

## 11. Done-when verification

- [ ] 11.1 A full renewal case resolves end to end through the graph,
      matching main-branch output for every golden scenario (ties back
      to 1.7, re-confirmed after all later steps).
- [ ] 11.2 The graph visualization file is present and reviewed (1.9).
- [ ] 11.3 The calibration table in design.md shows Step 2's isolated
      effect, confirming or refuting "reranking measurably improves the
      calibration set."
- [ ] 11.4 The embedding upgrade section shows either a completed
      migration with measured improvement, or a recorded RAM measurement
      justifying deferral — not silence either way.
- [ ] 11.5 The Docling comparison is recorded for all three PDFs in
      design.md, and the adoption decision (per PDF) follows directly
      from those measurements.
- [ ] 11.6 A Langfuse trace for one real conversation is captured
      (screenshot or exported JSON) showing graph transitions and tool
      calls, referenced from this change's record.
- [x] 11.7 RAGAS baseline scores are recorded in design.md — split into
      `average_all`/`average_answered`/`refusal_rate` per the user's
      correction that averaging refusals into quality scores conflates
      two separate defects.
- [ ] 11.8 CI is confirmed to fail on a deliberately regressed golden
      scenario (9.6) and to pass on the actual, unmodified suite.
- [ ] 11.9 Query latency is recorded before and after reranking (2.7),
      showing its effect on the citizen-waiting critical path explicitly.
