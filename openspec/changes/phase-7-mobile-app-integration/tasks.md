## 1. Backend: the one scoped addition (photo-studio-directory)

- [x] 1.1 Add `StudioOut` and `StudioResolutionOut` to `app/api/schemas.py`, mirroring `ResolvedStudio`/`StudioResolution` field-for-field (same `from_resolved` classmethod pattern every other `*Out` model uses)
- [x] 1.2 Add `app/api/studios.py`: `GET /studios` route, `district` query param, calls the existing `app.engine.studios.resolve_studios` unchanged, 422 on a missing/unrecognized district
- [x] 1.3 Register the new router in `main.py`
- [x] 1.4 Add a route-level test (district with studios, district with none, missing/invalid district → 422, citation and receipt-note presence)
- [x] 1.5 Run the existing backend test suite — confirm zero regressions to any other route (254 passed, 4 skipped, up from 249 before this change)

## 2. Backend: README and run-command documentation (no code changes)

- [x] 2.1 Document `uvicorn main:app --host 0.0.0.0 --reload` as the run command for LAN reachability, and why (`127.0.0.1`-only binding is unreachable from a phone)
- [x] 2.2 Document how to find the laptop's LAN IP (Windows: `ipconfig`, look for the LAN adapter's IPv4 address) for the mobile app's `.env`

## 3. Mobile: dependencies and configuration

- [x] 3.1 Add `expo-secure-store` to `package.json` (via `npx expo install`, SDK-54-compatible version; also added `expo-crypto` for `randomUUID()` — needed by Task 4.2's device-id generation)
- [x] 3.2 Add `.env.example` with `EXPO_PUBLIC_API_BASE_URL` (or the project's chosen env-var name) documented
- [x] 3.3 Add `src/api/config.ts`: reads the base URL from env, throws a clear, caught-at-startup error if unset (not a silent undefined that fails later as a confusing network error)
- [x] 3.4 README: LAN IP discovery steps, `.env` setup, and the backend run command from Task 2 (done together with 2.1/2.2)

## 4. Mobile: API client layer

- [x] 4.1 `src/api/types.ts` — hand-written types mirroring every response shape in `app/api/schemas.py`, plus the new `StudioResolutionOut`
- [x] 4.2 `src/api/deviceId.ts` — `getOrCreateDeviceId()` via `expo-secure-store` + `expo-crypto`'s `randomUUID()`
- [x] 4.3 `src/api/errors.ts` — `NetworkError`/`UnreachableError`/`ServerError` classes and the classifier that produces one from a failed `fetch` (uses `expo-network`, newly added, to distinguish device-offline from backend-unreachable)
- [x] 4.4 `src/api/client.ts` — `postChatMessage`, `getNextQuestion`, `postResolve`, `getServices`, `getTranscript`, `getStudios`; every function returns a typed success value or throws one of the three error classes (`postResolve`'s 409 is a meaningful not-ready result, not a thrown error)
- [x] 4.5 Unit tests for the error classifier and client request classification (network failure vs. unreachable vs. 5xx vs. success vs. 409) using a mocked `fetch` — 11 tests passing. Note: no test runner existed in this repo at all before this task (README's "Jest" listing was aspirational); added `jest`/`jest-expo`/`@types/jest` and minimal config as a necessary prerequisite.

## 5. Mobile: state

- [x] 5.1 `src/store/deviceStore.ts` — device id (loaded once at startup via Task 4.2), active `case_id`, selected service (for the context bar), transcript messages, loading/error state for the active chat turn
- [x] 5.2 `src/store/planStore.ts` — last resolve response, loading/error state for resolve and for the studios fetch
- [x] 5.3 App-startup sequence: load device id → call `GET /chat/transcript` → populate `deviceStore` with any existing case/messages before the Services screen renders

## 6. Mobile: PlanHeader component (new — see design.md's finding)

- [x] 6.1 `src/components/PlanHeader.tsx` — `{fee, offices, conflictNote?}` props, extracted from `PlanScreen.tsx`'s current inline `PlanStat`/`PlanDivider`, tokens-only styling, no timeline prop (no backend field supplies one)
- [x] 6.2 Export from `src/components/index.ts`

## 7. Mobile: Services screen — Tab 1 (Services)

- [x] 7.1 Replace the four hardcoded mock services with `getServices()` — loading/empty/error/loaded states
- [x] 7.2 Service card: name (from API) + static "who it's for" line (design.md finding 3, sourced from proposal.md's own per-service descriptions) + flat fee where one genuinely exists (amendment, child-deletion, emergency certificate) or a "fee depends on your situation" qualifier otherwise
- [x] 7.3 Tapping a card: set `deviceStore`'s selected service, hide the list, show the context bar with the service name and a "Change" affordance, transition to chat, send the opening turn

## 8. Mobile: Services screen — Tab 2 (Ask) and chat rendering

- [x] 8.1 Ask tab opens chat directly with no service pre-selected (no context bar)
- [x] 8.2 Render `next_question.display_text` (never `.prompt`); render `next_question.hint` beneath it in muted, smaller text when present
- [x] 8.3 Render `acknowledgement` as an assistant message before the next question when present
- [x] 8.4 Render a grounded answer's `citations` via the existing `SourceCitation` component; render an ungrounded answer's text as a plain assistant message with no error styling
- [x] 8.5 Cross-service handling: render any answer as returned, re-show the same pending question afterward, never touch the context bar's selected service from a chat response (design.md's cross-service decision — no automatic switch detection this phase; a citizen changes service only via the "Change" affordance)
- [x] 8.6 Thinking indicator: visible from send to response for every chat turn
- [x] 8.7 Send-turn error handling: on `NetworkError`/`UnreachableError`/`ServerError`, show the matching distinct message with retry, keep the citizen's typed message recoverable (not lost) so retry doesn't require retyping

## 9. Mobile: transcript restore

- [x] 9.1 On app load, render `deviceStore`'s populated transcript (from Task 5.3) before any new message is sent
- [x] 9.2 A device with no prior case renders an empty chat, no error

## 10. Mobile: Plan screen

- [x] 10.1 Replace `PlanScreen.tsx`'s hardcoded `INITIAL_ITEMS` and inline header with `planStore`'s resolve response and the new `PlanHeader` (Task 6)
- [x] 10.2 Render requirements ordered by `sequence`; prerequisite-kind visually distinct from document-kind (reusing `ChecklistItem`'s existing variant mechanism, extended if needed — string-union, not a boolean)
- [x] 10.3 `SourceCitation` under each requirement from its own `citation`
- [x] 10.4 Render each requirement's `resources` as tappable links (label + type); render any A4/laser-print note from the requirement's detail text alongside them
- [x] 10.5 Fetch and render `getStudios(district)` once the district is known; render the response's studio list and receipt note; explicit empty state for a district with none
- [x] 10.6 Render `offices.conflict_note` prominently, unconditionally visible (no extra tap)
- [x] 10.7 Render `amendment_alternative`, when present, as a side-by-side comparable choice with its own fee and requirements — not below the fold of the primary plan
- [x] 10.8 Render `scope_gate.reason` in place of the entire checklist/fee/office section when `scope_gate` is non-null — verify no requirement/fee/office section renders in this case
- [x] 10.9 Plan-screen loading/empty/error states for the resolve call itself, distinct from the studios fetch's own four states

## 11. Verification

- [x] 11.1 Backend test suite passes with the new `/studios` route (Task 1.5) — 254 passed, 4 skipped, re-run after the mobile work above; zero regressions
- [ ] 11.2 Manual run on a physical device over LAN: confirm the app reaches the backend, confirm the unreachable-backend error state by pointing the config at a wrong IP momentarily
- [ ] 11.3 Walk every spec scenario in `specs/mobile-app-integration/spec.md` and `specs/photo-studio-directory/spec.md` against the running app; note any that fail
- [ ] 11.4 Confirm each of proposal.md's "Done When" criteria directly: all seven services listed and startable, a name-change case shows the amendment alternative, an overseas case shows the Overseas Missions form set, a conflict_note displays, a greeting reads as an orientation not an error, closing/reopening restores the transcript, all four states render on chat/services/plan/studios
