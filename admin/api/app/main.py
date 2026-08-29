"""admin-dashboard change, task 2.1 — `/admin/api`'s own, standalone
FastAPI application. No import of anything under `/api/app` other than
`app.models`'s deliberate schema re-export (see that module's
docstring) — no shared router, dependency, or process with the
citizen-facing app. See design.md's "Two fully separate applications,
sharing only the database" decision.
"""

from fastapi import FastAPI

from app.routes import auth, dashboard, health, plans_audit, rules, services, sources

app = FastAPI(title="GovAssist Admin Dashboard API")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(rules.router)
app.include_router(dashboard.router)
app.include_router(services.router)
app.include_router(sources.router)
app.include_router(plans_audit.router)
