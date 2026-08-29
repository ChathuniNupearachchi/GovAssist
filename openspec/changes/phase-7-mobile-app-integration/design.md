## Context

See proposal.md for motivation. Current state, confirmed directly
against the running code (not assumed) before writing this design:

**Backend routes today** (`api/main.py`, `app/api/*.py`):
`POST /chat/message` (`{message, case_id?, device_ref?}` →
`ChatMessageResponse{case_id, answer?, next_question?, acknowledgement?}`),
`GET /case/{id}/next-question` (→ `QuestionOut | null`),
`POST /case/{id}/resolve` (→ `CaseResolutionOut`, 409 with
`{detail}` when not ready), `GET /services` (→ `ServiceOut[]`),
`GET /requirements/{id}` (→ `RequirementOut`), `GET /chat/transcript?
device_ref=` (→ `TranscriptOut`). No CORS middleware is configured —
irrelevant for the native app (CORS is a browser mechanism; React
Native's `fetch` is not subject to it) but would matter for `expo
start --web`, which this phase does not target.

**Mobile app today**: `src/api/` and `src/store/` are empty placeholder
directories — this phase is the first to populate them. `expo-secure-
store` is not yet a dependency. `PlanScreen.tsx` has its fee/office/
timeline header inlined as local `PlanStat`/`PlanDivider` functions, not
a `PlanHeader` component — CLAUDE.md's component inventory listing
`PlanHeader` as already built does not match the repo; this phase
builds it for the first time, not a "reuse" case for that one component.

**Three findings that changed this design from the request as written**,
confirmed with the user before proceeding:

1. **No `/studios` endpoint or `studios` field exists anywhere.** The
   engine-level work is already done — `app.engine.studios.
   resolve_studios(db, district)` and its `ResolvedStudio`/
   `StudioResolution` dataclasses exist, tested nowhere, wired to no
   route. Confirmed with the user: add one new minimal route
   (`GET /studios?district=`) as a scoped, explicit exception to "no
   backend changes" — see `photo-studio-directory`'s spec.
2. **No structured intent signal exists for greeting vs. the three
   out-of-scope sub-cases the request describes.** Searched the backend
   for `out_of_scope`/`other_department`/`not_government` classification
   — none exists. The only real signal is `answer.grounded` (bool); a
   greeting is packaged today as `RAGResponse(text=GREETING_ORIENTATION_
   MESSAGE, citations=[], grounded=True)` (`app/graph/build.py`) — the
   same shape as a real cited answer, just with an empty citation list.
   Confirmed with the user: the frontend renders from this real binary
   signal (grounded-with-citations vs. ungrounded-plain-non-answer), and
   does not fabricate four categories the backend does not distinguish.
   `mobile-app-integration`'s spec is written to this reality.
3. **`ServiceOut` carries only `{id, code, name, category}`** — no
   audience ("who it's for"), timeline, or fee. Fee and timeline are
   also genuinely case-dependent for several services (validity tier,
   normal/urgent, penalty tiers) — a single number on a service card
   would misrepresent them before intake even starts. Not raised as a
   user question (doesn't change scope or acceptance criteria, unlike
   the two above) — resolved here: service cards show name plus a
   short, static, presentational "who it's for" line maintained in the
   app (from proposal.md's own service descriptions — content, not
   computed data) and, where a service has one genuinely flat fee
   (amendment LKR 1,200, child-deletion LKR 1,200, emergency
   certificate LKR 500), that flat figure; every other service shows a
   qualifier ("fee depends on your situation") rather than a misleading
   single number. No timeline shown on the card — timeline is
   unconfirmed in the API for most services, per `design.md`s upstream
   BACKEND_PLAN.md research, and not worth fabricating.

## Goals / Non-Goals

**Goals:**
- Wire all five existing screens to the live API with the seven
  services, using the seven read/write endpoints above (six existing
  plus the one new `/studios` route).
- Render every field `POST /case/{id}/resolve` actually returns,
  including the ones the current screen has no concept of.
- Make the four-state contract (loading/empty/error/loaded) and the
  three distinct error messages (network/unreachable/500) real,
  reusable patterns other screens can follow later, not one-off
  handling per screen.

**Non-Goals:**
- No changes to `case-api`'s existing routes/shapes.
- No new `intent`/out-of-scope classification field on the backend —
  see finding 2 above.
- No real citizen authentication — device identity only, per CLAUDE.md's
  "no citizen accounts" scope; Login screen's Google/email UI stays
  cosmetic (skip-through), unchanged in behavior.
- No offline support, no local caching layer beyond what Zustand holds
  in memory for the running session.
- No changes to the three disabled "Coming Soon" departments.

## Decisions

### API client: one typed module, hand-written types from the actual schemas

`src/api/types.ts` mirrors `app/api/schemas.py`'s Pydantic models
field-for-field (not generated — no OpenAPI codegen tool is in this
project's dependency set, and the schema surface is small and stable
enough that hand-written types are lower-risk than adding a codegen
step this phase). `src/api/client.ts` exports one function per endpoint
(`postChatMessage`, `getNextQuestion`, `postResolve`, `getServices`,
`getTranscript`, `getStudios`), each doing: build URL from
`config.apiBaseUrl`, `fetch` with JSON headers, distinguish a network-
level failure (fetch throws) from an HTTP error status (fetch resolves,
`response.ok` is false) from a successful parse — the three cases the
error-message spec requires the UI to tell apart. `GET /requirements/
{id}` is deliberately NOT wrapped — nothing in the wired screens needs
to fetch a single requirement independently; `resolve`'s own response
already embeds full `RequirementOut` objects. If a future screen needs
it, it's a one-function addition, not a design change.

**Alternative considered**: generate types from FastAPI's OpenAPI
schema (`/openapi.json`) via a codegen tool. Rejected for this phase —
adds a new dev dependency and a build step for a schema surface small
enough to hand-maintain accurately (7 endpoints, 6 response shapes),
and the three findings above mean blind codegen would need manual
correction anyway (the studios route doesn't exist until this change
adds it).

### Device identity: SecureStore-backed UUID, read once at app start

A single `src/api/deviceId.ts` module: `getOrCreateDeviceId()` reads
from `expo-secure-store`, generates via `expo-crypto`'s
`randomUUID()` (already available via Expo SDK 54, no new dependency)
and persists on first call. Read once at app startup (not per-request)
and held in memory for the session — SecureStore reads are async and a
few hundred ms; re-reading per request would add latency to every turn
for no benefit since the value never changes after first launch.

### State: two Zustand stores, not one

`src/store/deviceStore.ts` — device id, active `case_id`, the currently
selected service (for the context bar), transcript messages. Persists
`case_id` implicitly via the backend's own device-based case resumption
(`GET /chat/transcript`) rather than duplicating it in SecureStore —
one source of truth for "what case is active," not two that can drift.
`src/store/planStore.ts` — the last resolve response, kept separate from
`deviceStore` because plan data has a different lifecycle (cleared/
refetched on resolve, not on every chat turn) and because `PlanScreen`
and `ServicesScreen` shouldn't re-render on each other's state changes.

**Alternative considered**: one combined store. Rejected — the two
screens' update frequencies differ enough (chat: every turn; plan: only
on resolve) that combining them means either screen re-rendering on the
other's updates, or manual selector discipline that a split avoids by
construction.

### Cross-service questions: render from the response, never infer from local state

The backend already routes a cross-service question correctly (per
CLAUDE.md's own architecture — the tool-using agent decides, the
rules engine never guesses). The frontend's job is narrower than it
might seem: render `answer`/`next_question` exactly as returned, and
never branch UI logic on "does this answer match the selected
service" — there is no field to check that against, and inferring it
from message text would be exactly the kind of guessing CLAUDE.md's
architecture exists to avoid on the backend; the frontend should not
reintroduce it. The context bar's selected-service label lives in
`deviceStore`, set only by an explicit service-card tap or an accepted
switch-offer — never touched by a chat response.

A "suggested switch" is only detectable today via prose in `answer.text`
(no structured field for it either — same category of gap as finding
2). Given the spec's own scenario ("surface it as an offer... not an
automatic switch") requires the citizen to *see and accept* a specific
switch, and no structured signal exists to drive that safely without
false positives, this phase implements a manual path only: a citizen
can always tap "Change" on the context bar themselves after reading a
cross-service answer. Detecting a switch offer from response text is
deferred, not built on a guess — recorded as a real limitation now
rather than half-built.

### The `/studios` addition stays inside the studio directory's own scope

New: `app/api/studios.py` (one route), `StudioOut`/`StudioResolutionOut`
in `app/api/schemas.py` (mirroring `ResolvedStudio`/`StudioResolution`
field-for-field, same pattern every other `*Out` class already
follows), registered in `main.py`. No change to `resolve_case`,
`CaseResolutionOut`, or any other route — the app calls `GET /studios`
as its own request once it knows the citizen's district (from the
answered `district` question or the resolve response's implied
district), not as a resolve-response field.

### PlanHeader: extracted from PlanScreen's existing inline layout

`src/components/PlanHeader.tsx` takes `{fee, offices, conflictNote?}`
and renders exactly what `PlanScreen.tsx`'s current `PlanStat`/
`PlanDivider` functions already render inline — same visual design,
extracted so it's testable and reusable, per the "reuse existing
components" constraint's own spirit (this phase is the first time it
exists to reuse). Timeline is intentionally not a `PlanHeader` prop —
no resolve-response field carries it (finding 3's same root cause,
service-side) and the current design's "30 working days" was
hardcoded copy, not derived data; `PlanHeader` does not fabricate a
timeline where the API supplies none.

### Error taxonomy: three cases, one shared classifier

`src/api/client.ts` classifies every failure into exactly one of
`NetworkError` (fetch itself threw — no connectivity), `UnreachableError`
(fetch threw specifically as a connection failure to the configured
host — timeout/refused, distinguished from `NetworkError` by whether
`navigator`-equivalent connectivity info, where available via Expo's
`Network` module, says the device is online), or `ServerError` (fetch
resolved with a 5xx). Each screen's error state renders from this one
shared type rather than re-deriving the distinction per call site.

## Risks / Trade-offs

- **[Risk] The `/studios` addition, however minimal, is still a
  backend change in a phase whose own constraint says "no backend
  changes."** → Mitigation: scoped to one new file, one route, zero
  changes to any existing route/schema/engine function; explicitly
  confirmed with the user as the one deliberate exception, not a
  silent scope violation.
- **[Risk] Service cards showing a static "who it's for" line
  (finding 3) can drift from the backend's actual seeded rules if a
  service's eligibility changes later.** → Mitigation: sourced directly
  from proposal.md's own per-service descriptions (already the
  authoritative eligibility record); flagged in tasks.md as
  presentational copy to revisit if a future phase adds these fields to
  `ServiceOut`.
- **[Risk] Distinguishing `UnreachableError` from `NetworkError` via
  Expo's `Network` module's connectivity read can itself be wrong
  (a device can report "connected" to a network with no working
  route to the configured LAN IP).** → Mitigation: acceptable
  imprecision — worst case, an unreachable-LAN-IP failure is shown as
  a generic "can't reach the server" (still distinct from a 500),
  not miscategorized as "no internet" when the citizen's phone truly
  has none. The three-way distinction the spec requires is preserved;
  only the network/unreachable boundary has this edge case.
- **[Risk] No automated switch-offer detection (see the cross-service
  decision above) means a citizen who gets a cross-service answer must
  notice and tap "Change" themselves.** → Mitigation: acceptable for
  this phase — the alternative (guessing a switch from prose) risks a
  false "we think you meant a different service" prompt with no
  backend confirmation behind it, worse than requiring one extra tap.

## Open Questions

None — the two questions that would have changed scope, behavior, or
acceptance criteria (studios, intent signal) were resolved with the
user before this document was written; finding 3 (service card fields)
was a minor presentational decision, recorded above rather than left
open.
