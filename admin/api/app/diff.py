"""admin-dashboard change, task 4.3 — material-vs-cosmetic diff
classification between an approved rule payload and a draft one.

Per design.md's "Material vs. cosmetic diff classification" decision: a
difference is **material** when it touches a fee amount/currency, or a
`document`-kind requirement's label (added, removed, or reworded);
every other difference (a `step`/`prerequisite` label reworded, or a
`sequence` reorder with no requirement added or removed) is
**cosmetic**. Both payload shapes are the same dict shape
`ADMIN_DRAFT.payload` and the approved-side query builder in
`app.routes.rules` produce: `{"requirements": [...], "fee": {...} |
None}`, each requirement a `{"id", "label", "kind", "sequence", ...}`
dict.
"""

from __future__ import annotations

from typing import Any, Literal

DiffEntry = dict[str, Any]

_MATERIAL_FEE_FIELDS = ("base_amount", "currency", "penalty_amount")


def _fee_diffs(approved_fee: dict | None, draft_fee: dict | None) -> list[DiffEntry]:
    diffs: list[DiffEntry] = []
    for field in _MATERIAL_FEE_FIELDS:
        approved_value = approved_fee.get(field) if approved_fee else None
        draft_value = draft_fee.get(field) if draft_fee else None
        if approved_value != draft_value:
            diffs.append(
                {
                    "field": f"fee.{field}",
                    "approved_value": approved_value,
                    "draft_value": draft_value,
                    "materiality": "material",
                }
            )
    return diffs


def _requirement_key(requirement: dict) -> str:
    # Falls back to label when a requirement has no stable "id" (e.g. a
    # hand-crafted draft that hasn't been persisted as a live row yet).
    return str(requirement.get("id") or requirement.get("label"))


def _requirement_materiality(requirement: dict) -> Literal["material", "cosmetic"]:
    return "material" if requirement.get("kind") == "document" else "cosmetic"


def _requirement_diffs(
    approved_requirements: list[dict], draft_requirements: list[dict]
) -> list[DiffEntry]:
    approved_by_key = {_requirement_key(r): r for r in approved_requirements}
    draft_by_key = {_requirement_key(r): r for r in draft_requirements}
    diffs: list[DiffEntry] = []

    for key in sorted(set(approved_by_key) | set(draft_by_key)):
        approved = approved_by_key.get(key)
        draft = draft_by_key.get(key)

        if approved is None:
            diffs.append(
                {
                    "field": f"requirement[{key}]",
                    "approved_value": None,
                    "draft_value": draft.get("label"),
                    "materiality": _requirement_materiality(draft),
                }
            )
            continue
        if draft is None:
            diffs.append(
                {
                    "field": f"requirement[{key}]",
                    "approved_value": approved.get("label"),
                    "draft_value": None,
                    "materiality": _requirement_materiality(approved),
                }
            )
            continue

        if approved.get("label") != draft.get("label"):
            diffs.append(
                {
                    "field": f"requirement[{key}].label",
                    "approved_value": approved.get("label"),
                    "draft_value": draft.get("label"),
                    "materiality": _requirement_materiality(draft),
                }
            )
        if approved.get("sequence") != draft.get("sequence"):
            diffs.append(
                {
                    "field": f"requirement[{key}].sequence",
                    "approved_value": approved.get("sequence"),
                    "draft_value": draft.get("sequence"),
                    "materiality": "cosmetic",
                }
            )

    return diffs


def classify_differences(approved: dict, draft: dict) -> list[DiffEntry]:
    """Returns every difference between an approved payload and a draft
    one (both `{"requirements": [...], "fee": {...} | None}`), each
    tagged `material` or `cosmetic` per the rule above."""
    return _fee_diffs(approved.get("fee"), draft.get("fee")) + _requirement_diffs(
        approved.get("requirements", []), draft.get("requirements", [])
    )
