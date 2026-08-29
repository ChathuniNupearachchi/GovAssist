"""admin-dashboard change: re-exports the citizen system's ORM model
classes (`api/app/models.py`) as `app.models` within this package, so
every admin route module can `from app.models import Service,
RuleVersion, ...` — the same import shape the rest of this project's
FastAPI apps use.

Loaded via `importlib.util` under a distinct module name rather than a
plain `sys.path` insert + `import app.models`, because this package is
itself named `app`. A path-insert-then-import would resolve
`app.models` against *this* package (which has no `models.py` of its
own) rather than the citizen system's, since Python caches `app` in
`sys.modules` the moment this package itself is imported — `api/app`
never gets a chance to satisfy the lookup. Loading the citizen file
under a private module name sidesteps that collision entirely.

This is a shared *schema definition*, not a shared *route or session* —
see `app/db/session.py`'s own docstring and design.md's "Two fully
separate applications, sharing only the database" decision. The
citizen-facing app never imports anything from `/admin`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[3] / "api"
_MODELS_PATH = _API_ROOT / "app" / "models.py"

_spec = importlib.util.spec_from_file_location("govassist_citizen_models", _MODELS_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Could not locate the citizen system's models.py at {_MODELS_PATH}")
_citizen_models = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("govassist_citizen_models", _citizen_models)
_spec.loader.exec_module(_citizen_models)

# Re-export every ORM class an admin route or test touches.
Base = _citizen_models.Base
Service = _citizen_models.Service
SourceDocument = _citizen_models.SourceDocument
RuleVersion = _citizen_models.RuleVersion
Office = _citizen_models.Office
Requirement = _citizen_models.Requirement
Question = _citizen_models.Question
Condition = _citizen_models.Condition
RequirementCondition = _citizen_models.RequirementCondition
FeeRule = _citizen_models.FeeRule
Case = _citizen_models.Case
CaseAnswer = _citizen_models.CaseAnswer
PlanItem = _citizen_models.PlanItem
DocumentChunk = _citizen_models.DocumentChunk
AuthorizedStudio = _citizen_models.AuthorizedStudio
ChatMessage = _citizen_models.ChatMessage
AdminUser = _citizen_models.AdminUser
AdminAction = _citizen_models.AdminAction
AdminDraft = _citizen_models.AdminDraft
AdminOverlay = _citizen_models.AdminOverlay
