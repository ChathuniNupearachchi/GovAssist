"""6.11.1 Tool wrappers + JSON schemas.

Every handler here is a thin wrapper over an existing `app.engine.*` /
`app.rag.retrieval` function — read-only, no new business logic. The
model (via `app.chat.agent`) selects which of these to call; the
function computes the answer. Every fee, office, timeline, or
requirement value a citizen sees in a tool-composed answer traces back
to one of these results — see the agentic-tool-answering spec's "Every
plan-shaped value in a response comes from a tool result" requirement.

Each handler returns a plain, JSON-serializable dict — never raises for
an expected "not found"/"not ready" case (those are structured results
the model can react to); only a genuinely malformed call (missing/wrong-
typed argument) is caught by `call_tool` and turned into a tool-error
result instead of propagating, per 6.11.1's "a malformed tool call does
not crash the turn" requirement.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.fees import resolve_fee
from app.engine.next_question import next_question as _next_question
from app.engine.offices import resolve_offices
from app.engine.renewal_intake import ATTRIBUTE_BY_PROMPT
from app.engine.requirements import resolve_requirements
from app.engine.resolver import (
    AMENDMENT_SERVICE_CODE,
    RENEWAL_SERVICE_CODE,
    _amendment_alternative,
    _approved_rule_version,
    resolve_case as _resolve_case,
)
from app.engine.types import Citation, IncompleteCaseError, ResolvedFee, ResolvedRequirement
from app.models import Case, CaseAnswer, Question
from app.rag.retrieval import retrieve

_SERVICE_CODES = {"renewal": RENEWAL_SERVICE_CODE, "amendment": AMENDMENT_SERVICE_CODE}


def _iso(value: datetime | None) -> str | None:
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
    return {
        "basis": fee.basis,
        "base_amount": fee.base_amount,
        "citation": _citation_dict(fee.citation),
    }


def _requirement_dict(requirement: ResolvedRequirement) -> dict[str, Any]:
    return {
        "id": str(requirement.id),
        "label": requirement.label,
        "kind": requirement.kind,
        "sequence": requirement.sequence,
        "citation": _citation_dict(requirement.citation),
        "resources": requirement.resources or [],
    }


def _answers_dict(db: Session, case_id: uuid.UUID) -> dict[str, str]:
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


def _get_case(db: Session, case_id: str) -> Case | None:
    try:
        return db.get(Case, uuid.UUID(case_id))
    except (ValueError, TypeError):
        return None


RETRIEVE_TOP_K = 8


def retrieve_documents(db: Session, query: str) -> dict[str, Any]:
    """Wraps `app.rag.retrieval.retrieve` — ranked chunks with source
    URLs and verified dates, no internal score/distance leaked to the
    model.

    Uses a wider top_k than retrieval's own default (5): the agent is
    doing more synthesis work than Phase 5/6.7's single-shot generation
    did (which cited every retrieved chunk unconditionally, masking a
    thin top-5 with an always-confident answer). A stricter, verifying
    agent needs a wider candidate pool so a genuinely descriptive chunk
    lower in the ranking (e.g. explanatory prose on a different page
    than the one a query's keywords most directly match) is still
    available to it.
    """
    result = retrieve(db, query, top_k=RETRIEVE_TOP_K)
    if not result.relevant:
        return {"relevant": False, "chunks": []}
    return {
        "relevant": True,
        "chunks": [
            {
                "chunk_id": str(c.chunk.id),
                "text": c.chunk.chunk_text,
                "source_document_id": str(c.source_document.id),
                "source_url": c.source_document.source_url,
                "verified_at": _iso(c.source_document.approved_at),
            }
            for c in result.chunks
        ],
    }


def get_fee(db: Session, service: str, urgency: str, age: float | None = None) -> dict[str, Any]:
    """Wraps `app.engine.fees.resolve_fee`. `service` is "renewal" or
    "amendment"; `urgency` is "normal" or "urgent". `age`, when given,
    selects an age-tiered fee where one exists (e.g. the renewal
    service's below-16 rate) instead of the default adult rate —
    without it, `resolve_fee` always returns the unconditional
    (adult-rate) fee rule."""
    service_code = _SERVICE_CODES.get(service)
    if service_code is None:
        return {"error": f"Unknown service '{service}' — expected 'renewal' or 'amendment'."}
    if urgency not in ("normal", "urgent"):
        return {"error": f"Unknown urgency '{urgency}' — expected 'normal' or 'urgent'."}

    rule_version = _approved_rule_version(db, service_code)
    fee = resolve_fee(db, rule_version.id, basis=urgency, age=age)
    if fee is None:
        return {
            "found": False,
            "message": f"No {urgency} fee rule exists for {service}.",
        }
    return {"found": True, "fee": _fee_dict(fee)}


def find_office(db: Session, district: str | None, urgent: bool) -> dict[str, Any]:
    """Wraps `app.engine.offices.resolve_offices`."""
    resolution = resolve_offices(db, district=district, basis="urgent" if urgent else "normal")
    return {
        "offices": [
            {"id": str(o.id), "name": o.name, "type": o.type} for o in resolution.offices
        ],
        "conflict_note": (
            {
                "note_text": resolution.conflict_note.note_text,
                "primary_citation": _citation_dict(resolution.conflict_note.primary_citation),
                "secondary_citation": (
                    _citation_dict(resolution.conflict_note.secondary_citation)
                    if resolution.conflict_note.secondary_citation is not None
                    else None
                ),
            }
            if resolution.conflict_note is not None
            else None
        ),
    }


def get_next_question(db: Session, case_id: str) -> dict[str, Any]:
    """Wraps `app.engine.next_question.next_question`. Read-only — never
    records anything."""
    case = _get_case(db, case_id)
    if case is None:
        return {"error": f"No case found with id '{case_id}'."}
    question = _next_question(db, case.service_id, _answers_dict(db, case.id))
    if question is None:
        return {"pending": False, "prompt": None}
    return {"pending": True, "attribute": ATTRIBUTE_BY_PROMPT.get(question.prompt), "prompt": question.prompt}


def _is_under_16(answers: dict[str, str]) -> bool:
    age = answers.get("age")
    return age is not None and float(age) < 16


def resolve_case(db: Session, case_id: str) -> dict[str, Any]:
    """Wraps `app.engine.resolver.resolve_case`. When intake isn't
    complete, returns a structured "not ready" result instead of
    raising — same check `app/api/cases.py`'s route makes. `resolve_case`
    itself now enforces the same completeness rule internally (raising
    `IncompleteCaseError`), so this pre-check and the `except` below are
    belt-and-suspenders, not two independent definitions of "ready"."""
    case = _get_case(db, case_id)
    if case is None:
        return {"error": f"No case found with id '{case_id}'."}

    answers = _answers_dict(db, case.id)
    if not _is_under_16(answers):
        pending = _next_question(db, case.service_id, answers)
        if pending is not None:
            return {"ready": False, "pending_question": pending.prompt}

    try:
        resolution = _resolve_case(db, answers)
    except IncompleteCaseError as exc:
        return {"ready": False, "pending_question": exc.pending_prompt}

    if resolution.scope_gate is not None:
        return {"ready": True, "scope_gate": resolution.scope_gate.reason}

    return {
        "ready": True,
        "requirements": [_requirement_dict(r) for r in resolution.requirements],
        "fee": _fee_dict(resolution.fee),
        "offices": (
            [{"id": str(o.id), "name": o.name, "type": o.type} for o in resolution.offices.offices]
            if resolution.offices is not None
            else []
        ),
    }


def compare_amendment_vs_renewal(db: Session, case_id: str) -> dict[str, Any]:
    """Both paths, always — computed unconditionally (not gated on
    `name_changed`), since a citizen asking this question is by
    definition still deciding. Renewal side uses the citizen's answers
    so far (basis/district); amendment side reuses the engine's existing
    `_amendment_alternative` computation, the same one `resolve_case`
    itself uses when `name_changed == "true"`."""
    case = _get_case(db, case_id)
    if case is None:
        return {"error": f"No case found with id '{case_id}'."}

    answers = _answers_dict(db, case.id)
    renewal_rv = _approved_rule_version(db, RENEWAL_SERVICE_CODE)
    renewal_fee = resolve_fee(db, renewal_rv.id, basis=answers.get("service_basis", "normal"))
    renewal_requirements = resolve_requirements(db, renewal_rv.id, answers)

    amendment = _amendment_alternative(db)

    return {
        "renewal": {
            "fee": _fee_dict(renewal_fee),
            "requirements": [_requirement_dict(r) for r in renewal_requirements],
        },
        "amendment": {
            "fee": _fee_dict(amendment.fee),
            "requirements": [_requirement_dict(r) for r in amendment.requirements],
        },
    }


# --- JSON tool schemas (Anthropic tool-use API shape) -----------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "retrieve_documents",
        "description": (
            "Search the approved Immigration & Emigration source documents for "
            "passages relevant to a query. Returns ranked chunks with source "
            "URLs and verified-as-of dates, or relevant=false if nothing "
            "relevant was found."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_fee",
        "description": (
            "The computed fee for a service and urgency, with its citation. "
            "Pass age when the citizen's age is known or the question is "
            "specifically about a minor's fee — some services have a "
            "separate, lower fee tier for applicants under 16; omitting age "
            "returns the standard adult-rate fee."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "enum": ["renewal", "amendment"]},
                "urgency": {"type": "string", "enum": ["normal", "urgent"]},
                "age": {"type": ["number", "null"]},
            },
            "required": ["service", "urgency"],
        },
    },
    {
        "name": "find_office",
        "description": (
            "The offices that accept applications for a district and urgency, "
            "plus any conflict note (e.g. urgent applications only being "
            "accepted at the Head Office)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district": {"type": ["string", "null"]},
                "urgent": {"type": "boolean"},
            },
            "required": ["urgent"],
        },
    },
    {
        "name": "get_next_question",
        "description": "The next attribute the rules engine still needs for this case, if any.",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
    },
    {
        "name": "resolve_case",
        "description": (
            "The full resolved plan for a case (requirements, fee, offices) — "
            "only once intake is complete. Returns ready=false with the still-"
            "pending question if intake isn't complete yet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
    },
    {
        "name": "compare_amendment_vs_renewal",
        "description": (
            "Both the amendment path and the full renewal path for a case — "
            "fee and requirements for each, computed independently, for "
            "comparing whether a citizen should amend their existing passport "
            "or apply for a new one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
    },
]

_HANDLERS = {
    "retrieve_documents": lambda db, args: retrieve_documents(db, args["query"]),
    "get_fee": lambda db, args: get_fee(db, args["service"], args["urgency"], args.get("age")),
    "find_office": lambda db, args: find_office(db, args.get("district"), args["urgent"]),
    "get_next_question": lambda db, args: get_next_question(db, args["case_id"]),
    "resolve_case": lambda db, args: resolve_case(db, args["case_id"]),
    "compare_amendment_vs_renewal": lambda db, args: compare_amendment_vs_renewal(db, args["case_id"]),
}


def call_tool(db: Session, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a model-requested tool call to its handler. A malformed
    call (unknown tool name, missing/wrong-typed argument) returns a
    structured tool-error result instead of raising — see module
    docstring and the agentic-tool-answering spec's "A malformed tool
    call does not crash the turn" requirement."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return handler(db, arguments)
    except (KeyError, TypeError, ValueError) as exc:
        return {"error": f"Malformed arguments for '{name}': {exc}"}
