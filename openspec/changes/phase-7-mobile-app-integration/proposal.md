## Why

The mobile app (five screens, seven components) runs entirely on
hardcoded mock data — four mock services, a fixed four-item checklist,
a scripted chat flow. The backend now serves seven real services
(renewal, new passport, lost/stolen, amendment, under-16, child-name-
deletion, emergency certificate) with conditional form sets,
applying-from-aware offices, an amendment alternative, conflict notes,
and a scope gate — none of which the app can show today. BACKEND_PLAN.md
Phase 7 is "done when a real conversation on the phone produces a real,
computed plan"; that requires wiring the existing screens to the live
API, not rebuilding them.

## What Changes

- Add `src/api/client.ts`: a typed client for every endpoint the app
  needs (`POST /chat/message`, `GET /case/{id}/next-question`,
  `POST /case/{id}/resolve`, `GET /services`, `GET /chat/transcript`,
  `GET /studios`), built from the actual FastAPI routes/schemas, not
  assumed.
- Add per-device UUID identity (Expo SecureStore), sent as `device_ref`
  on every request, resuming a returning device's active case.
- Add env-driven, LAN-reachable base-URL configuration with a documented
  setup path and an explicit unreachable-backend error state (never a
  silent hang).
- Populate the Services tab from `GET /services` (seven live services,
  not four mock ones); tapping a service pre-selects it for the Ask tab.
- Wire the Ask tab's chat to the live turn-by-turn API: rephrased
  question text (`display_text`, not `prompt`), hints, acknowledgements,
  cited answers, and one consistent non-error presentation for every
  ungrounded reply (see design.md's grounded/ungrounded finding —
  there is no backend signal distinguishing greeting from out-of-scope
  today, so the frontend does not pretend there is).
- Handle a citizen asking about a different service mid-intake: answer
  it, keep the original service's context bar and pending question, and
  surface a same-service switch as an offer, not an automatic change.
- Restore a returning device's transcript on load (`GET /chat/transcript`).
- Replace `PlanScreen`'s hardcoded checklist with the real
  `POST /case/{id}/resolve` response: computed fee, offices, ordered
  requirements with citations, tappable `resources` links (including
  the A4 laser-print note), `conflict_note` surfaced prominently,
  `amendment_alternative` presented as a real side-by-side choice, and
  `scope_gate` rendered as a plain refusal reason with no partial plan.
- Add a new `PlanHeader` component — listed in CLAUDE.md as already
  built, but not present in the repo; `PlanScreen.tsx` currently has
  the same layout inlined. Extracted once, per the "reuse existing
  components" constraint's own spirit, not rebuilt twice.
- Add `GET /studios?district=` — additive only, not breaking, and the
  one scoped exception to "no backend changes" (see design.md's
  studios finding, confirmed with the user) — so the 1,420-row
  `AuthorizedStudio` table (seeded, never exposed to any client today)
  can render on the Plan screen. No existing route or schema changes.
- Every chat/services/plan data surface handles all four states
  (loading, empty, error, loaded), with a visible "thinking" indicator
  during a chat turn and distinct plain-language messages for network
  failure, unreachable backend, and a 500.
- README: LAN IP discovery steps, `.env` setup, and the
  `uvicorn main:app --host 0.0.0.0 --reload` run command (a
  documentation addition, not a code change) so a phone on the same
  network can actually reach the API.

## Capabilities

### New Capabilities
- `mobile-app-integration`: the mobile app's behavior once wired to the
  live API — device identity, the services list and chat turn contract
  (question rendering, cross-service questions, transcript restore),
  the plan screen's rendering of every resolve-response field, and the
  four-state/error-handling contract every data surface follows.
- `photo-studio-directory`: `GET /studios?district=` and the district-
  scoped authorized-studio lookup it exposes — the one backend addition
  this change makes, kept minimal and read-only.

### Modified Capabilities
(none — `case-api`'s existing requirements are unchanged; this change
only adds a new, separate route alongside them)

## Impact

- **New**: `src/api/client.ts`, `src/api/types.ts` (response shapes),
  `src/store/deviceStore.ts` (or similar — device UUID + active case),
  `src/store/chatStore.ts`/`planStore.ts` (Zustand state for the wired
  screens), `src/components/PlanHeader.tsx`, `.env`/`.env.example`,
  `app/app/studios.py` (new backend route), README updates.
- **Modified**: `ServicesScreen.tsx` (mock chat → live API, seven
  services, cross-service handling), `PlanScreen.tsx` (hardcoded →
  resolve response), `app/main.py` (register the new studios router).
- **New dependency**: `expo-secure-store` (not currently installed).
- **Out of scope**: any change to `case-api`'s existing routes/shapes,
  any new `intent`-classification field on `ChatMessageResponse` (see
  design.md — the frontend works from the real binary grounded signal
  instead), Login screen's actual auth wiring (device identity only,
  per CLAUDE.md's "no citizen accounts" scope), the three disabled
  "Coming Soon" departments.
