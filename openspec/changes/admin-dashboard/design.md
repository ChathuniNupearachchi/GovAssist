## Context

GovAssist's citizen-facing system (`/api`, `/govassist`) already assumes
a human approval gate exists (CLAUDE.md, BACKEND_PLAN.md Phase 9) but
has never built the reviewer-facing half of it. Today, `RULE_VERSION.
status` is set by hand during development/seeding; nothing in the
running system currently produces a `draft` rule version or reads one.

This build is explicitly the reviewer-facing UI over that gate, kept
read-only against live data. See proposal.md for the full motivation and
scope boundary. This document covers how the separation is actually
enforced, how each dashboard feature computes its view, and what the
seed data looks like.

## Goals / Non-Goals

**Goals:**
- A reviewer can browse everything the approval gate concept requires
  seeing: services, sources, drafts, and the effect of a decision.
- The database itself, not application code, is the boundary preventing
  the dashboard from ever mutating citizen-facing data.
- The one seeded draft gives a real, demonstrable material comparison
  without requiring the LLM rule-parsing pipeline (BACKEND_PLAN.md 3.5,
  not yet built) to run.

**Non-Goals:**
- Wiring an approval decision to actually change `RULE_VERSION.status`,
  trigger re-embedding, invalidate caches, or flag live saved plans —
  BACKEND_PLAN.md Phase 9's "four consequences" of a real approval.
  Recorded here as the deliberate next step, not attempted in this
  build.
- A role system with genuinely different reviewer/approver permissions.
  `ADMIN_USER.role` exists and is accepted at signup, but nothing in
  this build gates behavior on its value (proposal.md, `admin-auth`
  spec) — building that distinction now would be scaffolding with no
  behavior behind it.
- Live ingestion triggering (scrape, extract, chunk, embed) from the
  dashboard's "add source" or "seed draft" actions.
- RAGAS or Langfuse views. Both already exist as their own tools
  (`ragas` in `api/requirements.txt`; the self-hosted Langfuse stack in
  `docker-compose.yml`) with their own interfaces suited to their own
  audience — an engineer assessing retrieval quality against a golden
  set, or debugging an LLM call trace. Neither answers a reviewer's
  actual question ("is this fee correct, and does this citation
  support it?"), which only a source-citation-first UI over the rules
  themselves can answer. Building a third, worse interface to the same
  underlying tools would not serve the reviewer and was explicitly
  ruled out by the request.

## Decisions

### Two fully separate applications, sharing only the database

`/admin` (React + Vite + TypeScript) and `/admin/api` (a second FastAPI
app) are new, standalone codebases — no shared router, dependency
import, or process with `/api` or `/govassist`. The only thing the two
systems share is the same Postgres database, accessed through two
different roles. This is the cheapest way to guarantee "citizen-facing
system entirely unaffected": there is no code path by which a request
to `/admin/api` can execute against `/api`'s route table, and taking the
admin app down entirely has zero effect on citizen traffic.

Alternative considered: mounting admin routes under the existing
FastAPI app behind an `/admin` prefix and a role check. Rejected per the
request's explicit "do not extend the citizen-facing app — separation
is the point," and because it would make the two systems' failure
domains, deploy cadence, and database roles harder to keep genuinely
independent over time.

### Database-level read-only enforcement via a dedicated Postgres role

A new role (`govassist_admin_readonly`) is created by the same Alembic
migration that adds the four admin-owned tables, since the role and its
grants are schema-adjacent, versioned, and need to exist before the
admin API can connect. The migration:

1. `CREATE ROLE govassist_admin_readonly LOGIN PASSWORD '<from env>';`
2. `GRANT SELECT ON <the fourteen listed live tables> TO
   govassist_admin_readonly;`
3. `GRANT SELECT, INSERT, UPDATE, DELETE ON admin_user, admin_action,
   admin_draft, admin_overlay TO govassist_admin_readonly;`
4. `GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO
   govassist_admin_readonly;` scoped only to what the admin-owned
   tables need (they use client-generated UUID primary keys like every
   other table in this schema — see `app/models.py`'s `_uuid_pk()` — so
   no sequence grant is actually required; included only if a future
   admin-owned column needs one).

`/admin/api` connects using a new `ADMIN_DATABASE_URL` environment
variable pointing at this role, mirroring `api/app/db/session.py`'s
existing `DATABASE_URL`-from-`.env` pattern but as a fully separate
engine/session in `/admin/api`'s own `db/session.py` — it does not
import or reuse `/api`'s session module, keeping the two database
connections (and their credentials) independent.

Verification (per proposal.md's explicit "attempted write failing with
a permission error" requirement): a test connects directly with the
admin role's credentials and issues `INSERT INTO service (...) VALUES
(...)`, asserting Postgres raises a permission-denied error — not an
application-level check, since the whole point is that the guarantee
holds even if application code has a bug.

### The four admin-owned tables

```
ADMIN_USER      (extended)  id, email, role, password_hash
ADMIN_ACTION                id, admin_id, action (approve|reject),
                             target_type, target_id, reason, created_at
ADMIN_DRAFT                 id, service_id, based_on_rule_version_id,
                             payload (JSONB — the draft's requirements/
                             conditions/fees, same shape the comparison
                             view needs), status (pending|approved|
                             rejected), created_at
ADMIN_OVERLAY                id, target_type (service|source_document),
                             target_id (nullable — null for a new
                             record the overlay itself represents),
                             operation (create|update|delete),
                             payload (JSONB), created_at
```

`ADMIN_DRAFT.payload` and `ADMIN_OVERLAY.payload` are JSONB rather than
normalized tables, matching this project's existing precedent for
dashboard-shaped, not citizen-resolution-shaped, structured data
(`Requirement.resources`, `ChatMessage.tool_trace` — both JSONB for the
same reason: the shape belongs to one view, not to the relational rules
model). `target_type`/`target_id` on `ADMIN_ACTION` and `ADMIN_OVERLAY`
follow the same polymorphic-reference pattern already used nowhere else
in this schema but is the standard shape for an audit-log table
attached to more than one kind of target (a rule version or draft for
`ADMIN_ACTION`; a service or source document for `ADMIN_OVERLAY`).

### Admin auth mirrors, but does not share, citizen auth

`app/auth/security.py` already establishes this project's pattern:
bcrypt directly (not `passlib`, noted there as having had bcrypt-backend
compatibility issues), PyJWT with HS256, a `<X>_SECRET_KEY` environment
variable. `/admin/api` re-implements this same pattern under its own
module, its own `ADMIN_JWT_SECRET_KEY`, and a shorter token lifetime (8
hours, a work session, versus the citizen app's 30 days for a mobile
app a citizen shouldn't be signed out of) — copied rather than imported,
because sharing the module would either share the secret (defeating the
"independent token space" requirement in the `admin-auth` spec) or
require threading a second secret through code that has no other reason
to know about the admin system.

### Extraction method is read from the ingestion cache, not a new column

`SOURCE_DOCUMENT` has no `extraction_method` column today — the actual
method (`pdfplumber`, a free-chain OCR stage, or `claude-api` as last
resort) is recorded per content hash in
`api/data/snapshots/*.extraction.json` by
`app/ingestion/pdf_extraction.py`'s `_write_extraction_cache`. Rather
than adding a column to a live table (which this build's read-only
posture argues against touching at all, even additively, until the
live approval pipeline itself is being wired up), `/admin/api` reads
`SOURCE_DOCUMENT.content_hash`, looks up the matching cache file
read-only from the filesystem, and surfaces its `method` field
alongside the row. An HTML-type source document (no extraction cache
entry, since extraction only applies to PDFs) shows no extraction
method, distinct from a PDF whose cache entry is missing or unreadable
(shown as "unknown" rather than silently blank, so a reviewer can tell
the two apart).

### Material vs. cosmetic diff classification

The side-by-side comparison classifies a difference between the
approved version's and the draft's requirements/conditions/fees as
**material** when it touches `FeeRule.base_amount`, `FeeRule.
penalty_amount`, `FeeRule.currency`, `Requirement.label` where the kind
is `document`, or `Requirement.office_id`; every other difference
(wording changes to a `step`/`prerequisite` label, `sequence` reordering
with no requirement added or removed) is **cosmetic**. This mirrors
BACKEND_PLAN.md 3.6's existing intended distinction ("Classify material
(fee, document, office) vs cosmetic (wording)") for the not-yet-built
change-detection stage — this dashboard is the first place that
distinction actually needs to render as UI, so its definition is fixed
here rather than left implicit.

### Outdated-plan computation

For each live `CASE` row with `resolved_at` set, the dashboard looks up
the `RULE_VERSION` its `PLAN_ITEM` rows reference and compares it
against the current `status = approved` `RULE_VERSION` for that case's
`service_id`. If they differ, the case is flagged outdated in the
dashboard's response — a computed field, never written back to `CASE.
outdated` (which exists on the live table already but is not touched by
this read-only build).

### Verifying "citizen-facing query returns exactly what it returned before"

The done-when criterion is satisfied by a script (documented in
tasks.md) that: (1) calls the citizen-facing `/case/{id}/resolve`
endpoint and saves the JSON response, (2) approves the seeded draft
through the admin dashboard, (3) calls the same citizen-facing endpoint
again and saves the response, (4) asserts the two JSON payloads are
byte-identical. This is the direct, explicit proof that approval in the
dashboard has zero effect on citizen-facing behavior, rather than an
inference from "we didn't write to that table."

## Risks / Trade-offs

- **[Risk]** A future contributor adds a citizen-facing feature that
  reads `ADMIN_OVERLAY`/`ADMIN_DRAFT`, silently coupling the two
  systems the migration deliberately separated → **Mitigation**: the
  admin-owned tables are documented in this design as dashboard-only;
  the citizen-facing app's own database role (unchanged by this
  migration) is never granted access to them, so such a feature would
  fail at the database level the same way an admin write to a live
  table does.
- **[Risk]** The extraction-method-from-cache-file approach breaks if
  `api/data/snapshots/` moves or a document's cache file is deleted
  independently of its `SOURCE_DOCUMENT` row → **Mitigation**: the
  source catalog shows "unknown" rather than erroring when a PDF's
  cache entry can't be found, so a missing file degrades one field, not
  the page.
- **[Risk]** Seeding one draft directly into `ADMIN_DRAFT` (rather than
  generating it through the not-yet-built LLM rule-parsing pipeline)
  means the demo draft's shape is hand-crafted and could drift from
  what a real pipeline-produced draft's `payload` JSON will eventually
  look like → **Mitigation**: `ADMIN_DRAFT.payload`'s shape is defined
  here to match exactly what `resolve_requirements`/`resolve_fee`
  already return (the same shape the citizen-facing engine produces),
  so a future real draft-producer has a concrete target to match, not a
  guess.
- **[Trade-off]** Read-only-against-live means "approve" in this build
  is necessarily a UI/audit-log action with no live effect, which could
  read as a toy to someone unfamiliar with the phased plan →
  **Mitigation**: this is recorded explicitly in proposal.md's Impact
  section and demonstrated, not hidden — the before/after identical-
  query proof is the evidence that this is a deliberate boundary, not a
  missing feature.

## Migration Plan

1. One new Alembic migration in `api/migrations/` (same database,
   existing migration chain) adding `ADMIN_ACTION`, `ADMIN_DRAFT`,
   `ADMIN_OVERLAY`, `ADMIN_USER.password_hash`, the
   `govassist_admin_readonly` role, and its grants.
2. A seed script (mirroring the existing `app/seed/phase*.py`
   convention) inserting the one demonstration `ADMIN_DRAFT` (renewal
   fee LKR 10,000 → LKR 12,000).
3. `/admin/api` and `/admin` are new applications with their own
   `requirements.txt`/`package.json` — no changes to `/api`'s or
   `/govassist`'s dependency manifests.
4. Rollback: the migration's `downgrade()` drops the three new tables,
   the added column, and revokes/drops the role — safe, since nothing
   in the citizen-facing system references any of them.

## Open Questions

- Exact deployment target for `/admin` (a second Railway service, or
  local-only for this submission) — does not change any spec,
  decision, or task here, since the build and its verification are
  identical either way; can be settled at deploy time.
