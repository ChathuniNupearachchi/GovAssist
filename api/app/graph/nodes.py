"""Task 1.3 — the four linear nodes: `classify`, `record_facts`,
`next_question`, `resolve`. Each is a thin wrapper over the existing
`app.chat.classifier` / `app.engine.*` functions — no reimplementation,
matching the same `_answers_dict` query `router.py`, `app/chat/tools.py`,
and `app/api/cases.py` each already duplicate independently.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.runnables import RunnableConfig
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.deterministic import (
    is_greeting,
    is_same_district_as_before as _is_same_district_as_before,
    try_deterministic_match,
)
from app.chat.classifier import classify as _classify
from app.engine.next_question import next_question as _next_question
from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT, PROMPT_BY_ATTRIBUTE
from app.engine.resolver import (
    SCOPE_GATE_UNDER_16,
    UNDER_16_SERVICE_CODE,
    resolve_case as _resolve_case,
)
from app.engine.types import (
    AmendmentAlternative,
    CaseResolution,
    Citation,
    IncompleteCaseError,
    OfficeResolution,
    ResolvedFee,
    ResolvedRequirement,
)
from app.graph.state import GraphState
from app.models import Case, CaseAnswer, Question
from app.observability.tracing import traced_node

# Covers every service's questions (renewal, new-applicant, lost/stolen)
# — see app.engine.renewal_intake.PROMPT_BY_ATTRIBUTE's own docstring
# for why this used to be RENEWAL_QUESTIONS-only and silently dropped a
# fact extracted for an attribute only a non-renewal service asks.
_PROMPT_BY_ATTRIBUTE = PROMPT_BY_ATTRIBUTE

# Bug fix (manual QA bug #3): short, plain-language, no jargon — states
# what GovAssist does and what to try next, without asking anything or
# starting intake itself. Kept short deliberately (CLAUDE.md's "generous
# spacing... outdoors on a phone" audience).
GREETING_ORIENTATION_MESSAGE = (
    "Hi! GovAssist helps you figure out exactly what you need for a Sri "
    "Lankan passport — renewal, amendment, and related questions.\n\n"
    "You can:\n"
    "- Tell me your situation (e.g. \"my passport expired last year\") "
    "and I'll ask a few quick questions to build your document checklist.\n"
    "- Ask a specific question (e.g. \"how much does a passport cost?\").\n\n"
    "What would you like to do?"
)


def _get_db(config: RunnableConfig) -> Session:
    return config["configurable"]["db"]


def _answers_dict(db: Session, case_id: uuid.UUID | str) -> dict[str, str]:
    rows = db.execute(
        select(CaseAnswer.value, Question.prompt)
        .join(Question, CaseAnswer.question_id == Question.id)
        .where(CaseAnswer.case_id == case_id)
    ).all()
    answers: dict[str, str] = {}
    for value, prompt in rows:
        attribute = ATTRIBUTE_BY_PROMPT.get(prompt)
        if attribute is not None:
            answers[attribute] = value
    return answers


def _is_under_16(answers: dict[str, str], service_code: str | None = None) -> bool:
    """False for `passport-under-16` regardless of age — that service's
    whole premise is a child under 16 (Phase 9 service #5), so the
    scope gate that exists to refuse a minor everywhere else must never
    fire for it. Bug found and fixed alongside `resolve_case`'s own
    `service_code`-conditional gate: this node-level short-circuit
    checks age BEFORE `resolve_case` is ever called, so fixing only
    `resolve_case` left every call site here still refusing a
    passport-under-16 conversation the instant age was recorded."""
    if service_code == UNDER_16_SERVICE_CODE:
        return False
    age = answers.get("age")
    return age is not None and float(age) < 16


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _citation_dict(citation: Citation) -> dict[str, Any]:
    return {
        "source_document_id": str(citation.source_document_id),
        "source_url": citation.source_url,
        "verified_at": _iso(citation.verified_at),
    }


def _fee_dict(fee: ResolvedFee | None) -> dict[str, Any] | None:
    if fee is None:
        return None
    return {"basis": fee.basis, "base_amount": fee.base_amount, "citation": _citation_dict(fee.citation)}


def _requirement_dict(requirement: ResolvedRequirement) -> dict[str, Any]:
    return {
        "id": str(requirement.id),
        "label": requirement.label,
        "kind": requirement.kind,
        "sequence": requirement.sequence,
        "citation": _citation_dict(requirement.citation),
        "resources": requirement.resources or [],
    }


def _offices_dict(offices: OfficeResolution | None) -> dict[str, Any] | None:
    if offices is None:
        return None
    return {
        "offices": [{"id": str(o.id), "name": o.name, "type": o.type} for o in offices.offices],
        "district_mapping_caveat": offices.district_mapping_caveat,
        "conflict_note": (
            {
                "note_text": offices.conflict_note.note_text,
                "primary_citation": _citation_dict(offices.conflict_note.primary_citation),
                "secondary_citation": (
                    _citation_dict(offices.conflict_note.secondary_citation)
                    if offices.conflict_note.secondary_citation is not None
                    else None
                ),
            }
            if offices.conflict_note is not None
            else None
        ),
    }


def _amendment_alternative_dict(alt: AmendmentAlternative | None) -> dict[str, Any] | None:
    if alt is None:
        return None
    return {
        "fee": _fee_dict(alt.fee),
        "requirements": [_requirement_dict(r) for r in alt.requirements],
    }


def _resolution_dict(resolution: CaseResolution) -> dict[str, Any]:
    """Fully JSON-serializable — this is what actually lands in the
    checkpointed graph state, never the raw `CaseResolution` dataclass
    (see design.md's "resolve" node decision: the checkpointer persists
    conversation position, not business objects)."""
    return {
        "requirements": [_requirement_dict(r) for r in resolution.requirements],
        "fee": _fee_dict(resolution.fee),
        "offices": _offices_dict(resolution.offices),
        "amendment_alternative": _amendment_alternative_dict(resolution.amendment_alternative),
    }


@traced_node("classify")
def classify_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Fetches the currently pending question, tries the deterministic
    pass against it, and falls back to Claude classification — the exact
    order `router.py::handle_message` uses (pending question computed
    *before* classification, so a bare deterministic answer token can be
    matched against the attribute it's actually pending for)."""
    if state["action"] != "message":
        return {}

    db = _get_db(config)
    case = db.get(Case, uuid.UUID(state["case_id"]))
    answers_before = _answers_dict(db, state["case_id"])
    pending = _next_question(db, case.service_id, answers_before)
    pending_attribute = ATTRIBUTE_BY_PROMPT.get(pending.prompt) if pending is not None else None

    message = state["message"]
    base = {"answers_before": answers_before, "pending_attribute": pending_attribute}

    if is_greeting(message):
        # Checked before the deterministic pending-question match too —
        # "help" while `profession` is pending would otherwise be
        # accepted as the literal profession text (profession always
        # accepts free text), which is exactly the wrong read of it.
        return {
            **base,
            "extracted": {},
            "intent": "greeting",
            "contains_question": False,
            "should_answer_via_rag": False,
            "greeting_message": GREETING_ORIENTATION_MESSAGE,
        }

    deterministic_value = None
    if pending_attribute == "photo_district" and _is_same_district_as_before(message):
        # Item 5's "default to the applying district" shortcut — a bare
        # "same"/"yes" means the district already given, not a literal
        # value the citizen has to retype.
        deterministic_value = answers_before.get("district") or None
    if deterministic_value is None and pending_attribute is not None:
        deterministic_value = try_deterministic_match(pending_attribute, message)

    if deterministic_value is not None:
        return {
            **base,
            "extracted": {pending_attribute: deterministic_value},
            "intent": "answer",
            "contains_question": False,
            "should_answer_via_rag": False,
        }

    classification = _classify(message, pending.prompt if pending is not None else None)
    extracted = classification.extracted_dict()
    contains_question = classification.contains_question

    # CRITICAL BUG FIX (production incident): while a question is
    # pending, a genuinely UNCLEAR/degraded classification (an
    # exception, or a below-threshold confidence — see classifier.py's
    # fix #2) must never fall through to "treat it as an unanswerable
    # question" — that used to route to the full tool-agent, which had
    # nothing to answer and returned "I don't have that information"
    # while the citizen was mid-sentence attempting to answer. Ask again
    # in plain language instead, and never invoke the agent for this
    # turn. Deliberately gated on `unclear` alone, NOT "nothing
    # extracted" — a confidently-classified "situation" message that
    # legitimately states no fact for the pending attribute (e.g. the
    # opening "i need to renew my passport", which has no age in it) is
    # a normal, well-understood turn, not an unclear one; it must fall
    # through to the ordinary next-question flow below, not trigger a
    # spurious "sorry, I didn't catch that" (regression caught during
    # this fix's own live verification — see this change's report).
    if pending_attribute is not None and classification.unclear:
        return {
            **base,
            "extracted": {},
            "intent": "unclear",
            "contains_question": False,
            "should_answer_via_rag": False,
            "reask_message": f"Sorry, I didn't catch that. {pending.prompt}",
        }

    return {
        **base,
        "extracted": extracted,
        "intent": classification.intent,
        "contains_question": contains_question,
        "should_answer_via_rag": contains_question or classification.intent == "question",
    }


@traced_node("record_facts")
def record_facts_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    if state["action"] != "message" or not state.get("extracted"):
        return {"answers_after": state.get("answers_before", {})}

    db = _get_db(config)
    case_id = state["case_id"]
    case = db.get(Case, uuid.UUID(case_id))

    for attribute, value in state["extracted"].items():
        prompt = _PROMPT_BY_ATTRIBUTE.get(attribute)
        if prompt is None:
            continue
        question = db.scalars(
            select(Question).where(
                Question.service_id == case.service_id, Question.prompt == prompt
            )
        ).first()
        if question is None:
            continue
        existing = db.scalars(
            select(CaseAnswer).where(
                CaseAnswer.case_id == case.id, CaseAnswer.question_id == question.id
            )
        ).first()
        if existing is not None:
            existing.value = value
        else:
            db.add(CaseAnswer(case_id=case.id, question_id=question.id, value=value))
        db.flush()

    return {"answers_after": _answers_dict(db, case_id)}


@traced_node("next_question")
def next_question_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Shared by both entry paths. For `action="message"`, this simply
    computes the (possibly updated) next pending question. For
    `action="resolve"`, this is the readiness/under-16-first check
    `app/api/cases.py`'s resolve route already makes — age is evaluated
    before the pending-question gate, mirroring `resolve_case`'s own
    precedence (see `phase-6-api-routes`'s 8.4 completion note)."""
    db = _get_db(config)
    case_id = state["case_id"]
    case = db.get(Case, uuid.UUID(case_id))

    if state["action"] == "resolve":
        answers = _answers_dict(db, case_id)
        if _is_under_16(answers, service_code=case.service.code):
            # Scope-gate short-circuits straight through to `resolve` —
            # resolve_case itself produces the scope_gate response.
            return {"next_pending_question_id": None, "next_pending_question_prompt": None}
        pending = _next_question(db, case.service_id, answers)
        return {
            "next_pending_question_id": str(pending.id) if pending is not None else None,
            "next_pending_question_prompt": pending.prompt if pending is not None else None,
        }

    if state.get("intent") == "greeting" or state.get("reask_message"):
        # A greeting doesn't start or continue intake (bug fix — manual
        # QA bug #3); a reask_message already restates the pending
        # question in its own text (CRITICAL BUG FIX — production
        # incident), so no separate next_question is offered this turn
        # either — avoids showing the same question twice in one reply.
        return {"next_pending_question_id": None, "next_pending_question_prompt": None}

    answers_after = state.get("answers_after") or state.get("answers_before", {})
    # Bug fix: the scope gate used to only fire on the explicit resolve
    # action, so a message-turn intake kept asking further questions
    # (name_changed, dual_citizen, ...) for an under-16 case for as long
    # as the citizen kept answering, only refusing once resolve was
    # finally called. Check it here too, immediately once age<16 is
    # recorded — the very next response is the scope-gate message, not
    # another question.
    if _is_under_16(answers_after, service_code=case.service.code):
        return {
            "next_pending_question_id": None,
            "next_pending_question_prompt": None,
            "scope_gate_message": SCOPE_GATE_UNDER_16,
        }
    pending = _next_question(db, case.service_id, answers_after)
    return {
        "next_pending_question_id": str(pending.id) if pending is not None else None,
        "next_pending_question_prompt": pending.prompt if pending is not None else None,
    }


@traced_node("resolve")
def resolve_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """`action="resolve"` only — reached from `next_question_node` only
    once its readiness check has already passed (or the case is
    under-16). Mirrors `app/api/cases.py::resolve` exactly, including
    marking the case resolved on success."""
    db = _get_db(config)
    case_id = state["case_id"]
    case = db.get(Case, uuid.UUID(case_id))
    answers = _answers_dict(db, case_id)

    if not _is_under_16(answers, service_code=case.service.code) and state.get("next_pending_question_prompt") is not None:
        return {
            "resolution": {
                "ready": False,
                "pending_question": state["next_pending_question_prompt"],
            }
        }

    try:
        resolution = _resolve_case(db, answers, service_code=case.service.code)
    except IncompleteCaseError as exc:
        return {"resolution": {"ready": False, "pending_question": exc.pending_prompt}}

    case.resolved_at = datetime.now(timezone.utc)
    db.commit()

    if resolution.scope_gate is not None:
        return {"resolution": {"ready": True, "scope_gate": resolution.scope_gate.reason}}

    return {"resolution": {"ready": True, **_resolution_dict(resolution)}}
