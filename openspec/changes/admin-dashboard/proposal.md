## Why

GovAssist's architecture already assumes a human approval gate: scraped
content creates draft rule versions, and nothing reaches a citizen until
a human approves it (CLAUDE.md's "Scraped content never goes live
automatically"; BACKEND_PLAN.md Phase 9). That gate currently has no
reviewer-facing half — there is no way for a human to see a draft, compare
it against what's live, or record an approval decision. This change
builds that half: a separate, read-only admin dashboard that lets a
reviewer browse the seven live services, their source documents, and a
seeded draft rule change, and record approve/reject decisions — without
touching the live database or the citizen-facing system in any way.

Read-only against live data is a deliberate scope boundary for this
build, not an oversight: wiring an approval decision to actually change
`RULE_VERSION.status` in the live system is the remaining step, tracked
as such rather than attempted here.

## What Changes

- New standalone web application at `/admin` (React + Vite + TypeScript
  frontend) and `/admin/api` (a separate FastAPI app) — its own codebase,
  its own deployment, not an extension of the citizen-facing API or
  mobile app
- A dedicated Postgres role with `SELECT`-only grants on every table the
  citizen system reads, and `INSERT`/`UPDATE`/`DELETE` grants scoped only
  to four new admin-owned tables — enforced at the database level via
  `GRANT`/`REVOKE`, not by application-code convention
- Four new tables: `ADMIN_ACTION`, `ADMIN_DRAFT`, `ADMIN_OVERLAY`, plus
  `password_hash` added to the existing (currently-unused) `ADMIN_USER`
- Admin authentication: signup, signin, JWT-protected routes, bcrypt
  password hashing — mirroring the existing citizen-auth conventions in
  `app/auth/security.py` (bcrypt directly, PyJWT HS256) under the
  dashboard's own secret and token lifetime
- Dashboard home: counts of drafts pending review, unapproved sources,
  services with no approved rule version, and recently-approved items —
  operational status only, explicitly not a RAGAS or Langfuse view (see
  design.md for why neither serves a reviewer's actual question)
- Service management: all seven live services with real requirement/
  condition/question counts and citations, correctly shown as already
  **approved** (not pending) since they were hand-verified against
  source pages during development; create/update/delete on this view
  writes to `ADMIN_OVERLAY` and never touches live rule tables
- Source management: all live `SOURCE_DOCUMENT` rows with URL, status,
  fetch date, content hash, and **extraction method** (surfaced from the
  ingestion pipeline's per-document extraction cache, since
  `SOURCE_DOCUMENT` itself carries no such column today) — a
  Tesseract-derived extraction is visibly distinguishable from a
  text-layer one; adding a URL/PDF records intent in `ADMIN_OVERLAY` and
  is visibly marked as not triggering live ingestion
- Rule review (core feature, built first): a pending queue over
  `ADMIN_DRAFT` plus any live `RULE_VERSION` with `status = draft`, a
  side-by-side approved-vs-draft comparison with material changes (fee,
  document, office) visually distinguished from cosmetic ones, and
  approve/reject actions that record an `ADMIN_ACTION` without ever
  writing `RULE_VERSION.status`; a seeded draft (renewal fee LKR 10,000
  → LKR 12,000) gives the comparison view real material content to show
- Outdated-plan demonstration: a view over real saved `CASE` rows,
  computing (in the dashboard only, nothing written back) whether each
  case's resolved rule version has since been superseded
- Explicit before/after verification that a citizen-facing query returns
  identical results before and after an approval is recorded in the
  dashboard, and a demonstrated failed write against the read-only role

## Capabilities

### New Capabilities
- `admin-auth`: admin signup/signin, JWT issuance and verification,
  bcrypt password hashing, auth-required admin routes
- `admin-data-access`: the dedicated read-only Postgres role and its
  grants, the admin API's separate database connection, and the
  four admin-owned tables (`ADMIN_ACTION`, `ADMIN_DRAFT`,
  `ADMIN_OVERLAY`, `ADMIN_USER.password_hash`)
- `admin-dashboard-home`: the operational-status summary view
- `admin-service-catalog`: service listing, drill-down into a service's
  requirements/conditions/fees/questions with citations, and
  overlay-based create/update/delete
- `admin-source-catalog`: source document listing with extraction
  method, and overlay-based add-URL/upload-PDF intent recording
- `admin-rule-review`: the pending-draft queue, side-by-side comparison,
  material-vs-cosmetic change classification, and approve/reject
  recording
- `admin-plan-audit`: the outdated-saved-plan view computed against
  superseded rule versions

### Modified Capabilities
(none — every existing citizen-facing capability and spec is unchanged;
this change only adds new, separately-scoped capabilities and a new
read-only consumer of existing tables)

## Impact

- **New code**: `/admin` (frontend), `/admin/api` (backend) as fully
  separate applications; no changes to `/api` (the citizen-facing
  FastAPI app) or `/govassist` (the mobile app)
- **Database**: one new Alembic migration (in the citizen system's
  existing `api/migrations/`, since the tables it creates live in the
  same Postgres database) adding `ADMIN_ACTION`, `ADMIN_DRAFT`,
  `ADMIN_OVERLAY`, and `ADMIN_USER.password_hash`, plus the role/grant
  statements creating the dedicated read-only Postgres role
  (`govassist_admin_readonly` or similar) and the seed script inserting
  the one demonstration draft
- **No changes** to any existing table's schema, to `RULE_VERSION.status`
  semantics, to the citizen-facing API routes, or to any existing test
  — all existing tests must continue to pass unchanged
- **Explicitly deferred** (recorded in design.md, not built here): wiring
  an approval decision to actually publish a new `RULE_VERSION`,
  re-embedding, cache invalidation, or flagging live saved plans as
  outdated — this build computes and displays that state read-only;
  BACKEND_PLAN.md Phase 9's "four consequences" of a real approval
  remain a later step
