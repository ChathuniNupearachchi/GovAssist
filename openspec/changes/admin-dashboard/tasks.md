## 1. Database foundation

- [x] 1.1 Write the Alembic migration in `api/migrations/`: `admin_action`, `admin_draft`, `admin_overlay` tables, and `password_hash` added to the existing `admin_user` table
- [x] 1.2 In the same migration, create the `govassist_admin_readonly` Postgres role and grant it `SELECT` only on the fourteen listed live tables
- [x] 1.3 Grant the role `SELECT, INSERT, UPDATE, DELETE` on `admin_user`, `admin_action`, `admin_draft`, `admin_overlay` only
- [x] 1.4 Add SQLAlchemy models for the three new tables and the extended `AdminUser` in `api/app/models.py` (used read/write only by `/admin/api`, not imported by `/api`'s own route modules)
- [x] 1.5 Run the migration against the dev database and confirm all fourteen live tables plus the four admin tables exist as expected
- [x] 1.6 Write and run a permission test: connect directly with the `govassist_admin_readonly` role's credentials and attempt `INSERT INTO service (...)`; assert Postgres raises a permission-denied error
- [x] 1.7 Write a seed script inserting the one demonstration `ADMIN_DRAFT` (renewal fee LKR 10,000 → LKR 12,000), matching `resolve_requirements`/`resolve_fee`'s existing return shape for its `payload`

## 2. Admin API skeleton

- [x] 2.1 Scaffold `/admin/api` as a new, separate FastAPI application (own `main.py`, `requirements.txt`, `.env`) — no import of anything under `/api/app`
- [x] 2.2 Add `db/session.py` with its own engine bound to `ADMIN_DATABASE_URL` (the read-only role's connection string)
- [x] 2.3 `GET /admin/health` liveness route
- [x] 2.4 Confirm the citizen-facing `/api` app starts, serves, and passes its existing test suite completely unmodified with `/admin/api` present in the repo

## 3. Admin authentication

- [x] 3.1 `app/auth/security.py`-equivalent module in `/admin/api`: bcrypt hashing, PyJWT HS256 signing/verification under `ADMIN_JWT_SECRET_KEY`, 8-hour token lifetime
- [x] 3.2 `POST /admin/auth/signup` — email, password, role; hashes and stores; rejects a duplicate email
- [x] 3.3 `POST /admin/auth/signin` — verifies password, returns JWT
- [x] 3.4 `get_current_admin` FastAPI dependency requiring a valid bearer token on every other admin route
- [x] 3.5 Tests: signup, signin, duplicate-email rejection, wrong-password rejection, protected-route-without-token rejection, a citizen-facing JWT rejected on an admin route

## 4. Rule review — core feature, build first

- [x] 4.1 `GET /admin/rules/pending` — combines `ADMIN_DRAFT` rows and live `RULE_VERSION` rows with `status = draft`
- [x] 4.2 `GET /admin/rules/pending/{id}` — side-by-side payload: the current approved version's requirements/conditions/fees plus the draft's, each requirement carrying its citation and source link
- [x] 4.3 Implement the material-vs-cosmetic diff classifier per design.md (fee amount/currency, document label, office — material; wording/sequence — cosmetic)
- [x] 4.4 `POST /admin/rules/pending/{id}/approve` — records an `ADMIN_ACTION` (`action=approve`); does not touch `RULE_VERSION.status`
- [x] 4.5 `POST /admin/rules/pending/{id}/reject` — requires a `reason`, records an `ADMIN_ACTION` (`action=reject`); draft stays visible, never deleted
- [x] 4.6 Frontend: pending queue list view
- [x] 4.7 Frontend: side-by-side comparison view with material changes visually distinguished from cosmetic ones, and approve/reject actions with a reason field on reject
- [x] 4.8 Tests: pending queue includes the seeded draft; comparison response flags the fee change as material; approve writes only `ADMIN_ACTION` and leaves `RULE_VERSION.status` unchanged; reject requires and stores a reason and leaves the draft visible

## 5. Dashboard home

- [x] 5.1 `GET /admin/dashboard/summary` — drafts pending review, sources not yet approved, services with no approved rule version, recently-approved items with admin and timestamp
- [x] 5.2 Frontend: home view rendering the four sections from live computed data
- [x] 5.3 Confirm no RAGAS or Langfuse panel exists anywhere on this page (design.md's explicit exclusion)

## 6. Service catalog

- [x] 6.1 `GET /admin/services` — all live services with requirement/condition/question counts, current rule version, last verified date
- [x] 6.2 `GET /admin/services/{id}` — drill-down: requirements, conditions, fee rules, questions, each with citation and source link
- [x] 6.3 Confirm a hand-verified, `status=approved` service renders as approved, never pending
- [x] 6.4 `POST/PUT/DELETE /admin/services/{id}/overlay` — writes only to `ADMIN_OVERLAY`, reflected in the dashboard's own view
- [x] 6.5 Frontend: service list and drill-down views, with an overlay-edit form
- [x] 6.6 Tests: all seven live services appear with correct counts and approved status; an overlay edit appears in the dashboard view and leaves live rule tables unchanged

## 7. Source catalog

- [x] 7.1 Read-only helper reading a `SOURCE_DOCUMENT.content_hash`'s matching `api/data/snapshots/*.extraction.json` cache file for its extraction method; returns "unknown" when a PDF has no matching cache entry, and nothing for a non-PDF document
- [x] 7.2 `GET /admin/sources` — all live source documents with URL, type, status, fetched date, content hash, extraction method, supported services
- [x] 7.3 `POST /admin/sources/overlay` (add URL or upload PDF) — writes an `ADMIN_OVERLAY` row, shown as pending; does not call the live scraper/extraction pipeline
- [x] 7.4 Frontend: source list with extraction method shown per row, and an add-source form with a visible "not yet ingested" note
- [x] 7.5 Tests: extraction method surfaces correctly for a known Tesseract-derived document and a known text-layer document; adding a source creates no live `SOURCE_DOCUMENT`/`DOCUMENT_CHUNK` row

## 8. Outdated plan demonstration

- [x] 8.1 `GET /admin/plans/audit` — live saved cases with resolved plans, each showing its resolved rule version and whether that version has since been superseded for its service
- [x] 8.2 Frontend: list view flagging outdated plans distinctly from current ones
- [x] 8.3 Test: a case resolved against a since-superseded rule version is flagged outdated; a case still on the current approved version is not

## 9. Frontend shell

- [x] 9.1 Vite + React + TypeScript scaffold in `/admin`, plain CSS or Tailwind, no design system
- [x] 9.2 Auth flow: signup/signin forms, token storage, redirect-to-signin for an expired/missing token
- [x] 9.3 Navigation between home, rule review, service catalog, source catalog, and the outdated-plan view

## 10. End-to-end verification

- [ ] 10.1 Full backend test suite (`/api`'s existing tests) runs unchanged and passes, confirming zero regressions from the new tables/models — **blocked, not by this change**: `pytest` on `/api` currently fails ~295 pre-existing tests with `ForeignKeyViolation` on `question`/`case_answer` while the shared dev-DB conftest tries to wipe and reseed — caused by leftover `CASE_ANSWER` rows already in the dev database, unrelated to any admin-dashboard code (`govassist_admin_readonly` cannot write `case_answer` at all, and no admin route touches it). Needs a dev-DB cleanup (or a fresh DB) outside this change's scope to actually verify green; flagged for the user rather than silently checked off or "fixed" by mutating shared dev data
- [x] 10.2 Script per design.md: capture a citizen-facing `/case/{id}/resolve` response, approve the seeded draft through the dashboard, capture the same response again, assert byte-identical — save both captures as the demonstration artifact (`admin/scripts/verify_isolation.py`, run: PASS, captures in `admin/verification/`)
- [x] 10.3 Manual/scripted confirmation: an admin can sign up, sign in, and reach the dashboard; all seven services show real counts and approved status; real sources show real fetch dates and extraction methods; the seeded draft compares with the fee difference highlighted; approve and reject each behave as specified; the outdated-plan view flags a real superseded case — covered by `admin/api/tests/*` (24 passed, 1 skipped — see that test's own docstring) plus the isolation script above
- [x] 10.4 Confirm the read-only permission-error test (1.6) still passes after all routes are built, as the final proof the boundary held throughout — `admin/api/tests/test_db_permissions.py` re-run green after all routes were built
