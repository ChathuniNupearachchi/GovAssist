## Purpose

Defines the mobile app's behavior once wired to the live GovAssist API
in place of its current mock data — device identity, the services list
and chat turn contract, the plan screen's rendering of every field the
resolve response carries, and the four-state/error contract every data
surface follows, so a real conversation on a physical phone produces a
real, computed, citable plan.

## ADDED Requirements

### Requirement: A device identity persists across app launches
The app SHALL generate a UUID on first launch, persist it in Expo
SecureStore, and send it as `device_ref` on every request that accepts
one, so a returning device resumes its most recent unresolved case
instead of starting over.

#### Scenario: First launch generates and persists a device id
- **WHEN** the app launches with no device id yet stored
- **THEN** a new UUID is generated and persisted in SecureStore before
  any API request is made

#### Scenario: A returning device reuses its stored id
- **WHEN** the app launches and a device id is already in SecureStore
- **THEN** that same id is sent as `device_ref` on every request, and no
  new id is generated

### Requirement: The API base URL is configurable and unreachability is explicit
The app SHALL read its API base URL from environment-driven
configuration (not a hardcoded `localhost`), and SHALL surface an
explicit, distinct error state when the configured backend cannot be
reached, never a silent hang or an infinite loading spinner.

#### Scenario: A configured LAN URL is used
- **WHEN** the app is built with a LAN IP configured as the API base URL
- **THEN** every request targets that URL, not `localhost`

#### Scenario: An unreachable backend surfaces a distinct error
- **WHEN** a request to the configured base URL fails to connect at all
  (host unreachable, connection refused, or times out)
- **THEN** the app shows a distinct "can't reach the server" message
  with a retry affordance, not a generic error and not a silent hang

### Requirement: The Services tab lists every live service
The Services tab SHALL populate its list from `GET /services` rather
than hardcoded entries, rendering every service the API returns.

#### Scenario: All seven services render
- **WHEN** `GET /services` returns the seven seeded services
- **THEN** the Services tab shows seven service cards, not four

#### Scenario: The service list reflects only what the API returns
- **WHEN** the API returns N services, whatever N is
- **THEN** the Services tab shows exactly N cards — the list is never
  hardcoded independently of the response

### Requirement: Selecting a service pre-selects it for chat
Tapping a service card SHALL transition to chat with that service
pre-selected: the service list hides, a context bar names the selected
service with a "Change" affordance, and the first assistant message
appears.

#### Scenario: Tapping a service starts a pre-selected chat
- **WHEN** a citizen taps a service card
- **THEN** the list is replaced by chat, a context bar shows that
  service's name, and the conversation's first message appears without
  the citizen typing anything first

#### Scenario: The Ask tab opens with no service pre-selected
- **WHEN** a citizen opens the Ask tab directly (not via a service card)
- **THEN** chat opens with no context bar naming a specific service

### Requirement: A cross-service question does not break the selected intake
When a citizen asks about a service other than the one pre-selected,
the app SHALL render the answer normally, re-ask the still-pending
intake question afterward, and keep the context bar showing the
originally selected service. The app SHALL NOT assume every response
belongs to the pre-selected service, and SHALL NOT silently switch the
selected service — a backend-indicated switch is offered to the citizen
as a choice, never applied automatically.

#### Scenario: An off-topic answer does not interrupt intake
- **WHEN** a citizen mid-intake for one service asks a question that the
  backend answers about a different service
- **THEN** the answer renders normally and the same pending question for
  the originally selected service is shown again afterward

#### Scenario: The context bar does not silently change
- **WHEN** a cross-service answer is rendered
- **THEN** the context bar still names the originally selected service

#### Scenario: A suggested switch is offered, not applied
- **WHEN** the backend's response implies a different service actually
  applies to the citizen's situation
- **THEN** the app presents this as an offer the citizen can accept, and
  the selected service does not change unless the citizen accepts it

### Requirement: The next question's rephrased text is rendered, with its hint
The app SHALL render `next_question.display_text` as the question shown
to the citizen — never `next_question.prompt`, which is canonical text
for logging and tests only. When `next_question.hint` is present, it
SHALL render below the question in smaller, visually muted text.

#### Scenario: display_text is shown, not prompt
- **WHEN** `next_question.display_text` differs from `next_question.prompt`
- **THEN** the rendered question text is `display_text`

#### Scenario: A present hint renders below the question
- **WHEN** `next_question.hint` is non-null
- **THEN** it renders beneath the question, visually distinct (smaller,
  muted) from the question text itself

#### Scenario: An absent hint renders nothing extra
- **WHEN** `next_question.hint` is null
- **THEN** no hint text or empty space for one is rendered

### Requirement: An acknowledgement renders before the next question
When a chat turn's response includes a non-null `acknowledgement`, the
app SHALL render it as an assistant message before the next question in
that same turn.

#### Scenario: A present acknowledgement precedes the question
- **WHEN** a turn's response has both `acknowledgement` and
  `next_question` set
- **THEN** the acknowledgement message renders first, followed by the
  next question

#### Scenario: An absent acknowledgement renders nothing extra
- **WHEN** `acknowledgement` is null
- **THEN** no acknowledgement message is rendered for that turn

### Requirement: A cited answer renders its citations; an ungrounded answer renders as a plain non-answer
When a turn's response includes a non-null `answer`, the app SHALL
render `answer.text` with each of `answer.citations` shown using the
existing `SourceCitation` component when `answer.grounded` is true and
citations are present. When `answer.grounded` is false, the app SHALL
render the text plainly, as an ordinary assistant message — never
styled as an error state.

#### Scenario: A grounded, cited answer shows its sources
- **WHEN** a turn's `answer.grounded` is true and `answer.citations` is
  non-empty
- **THEN** each citation renders via `SourceCitation` beneath the answer
  text

#### Scenario: An ungrounded answer is not styled as a failure
- **WHEN** a turn's `answer.grounded` is false
- **THEN** `answer.text` renders as a normal assistant message, with no
  error styling, error icon, or retry affordance implying the app
  itself failed

#### Scenario: A grounded answer with no citations (e.g. a greeting) still renders normally
- **WHEN** `answer.grounded` is true and `answer.citations` is empty
- **THEN** `answer.text` renders as a normal assistant message with no
  citation list shown and no error styling

### Requirement: A returning device's transcript is restored on load
The app SHALL call `GET /chat/transcript` on load (using the device's
persisted `device_ref`) and render the returned message history before
the citizen sends anything, so closing and reopening the app does not
lose the conversation.

#### Scenario: A device with prior messages sees its history
- **WHEN** the app loads for a device with an existing transcript
- **THEN** every persisted message renders, in order, before any new
  message is sent

#### Scenario: A device with no prior case starts cleanly
- **WHEN** the app loads for a device with no active case
- **THEN** the transcript is empty and no error is shown for the empty
  result

### Requirement: The plan screen renders the full resolve response
The Plan screen SHALL replace hardcoded data with the live
`POST /case/{id}/resolve` response: the computed fee, the office list,
and the ordered requirement list (by `sequence`), with prerequisite-kind
requirements visually distinct from document-kind requirements, and
each requirement's citation rendered via `SourceCitation`.

#### Scenario: The plan renders from the resolve response
- **WHEN** a case resolves successfully
- **THEN** the Plan screen shows the resolve response's fee, offices,
  and requirements — not any hardcoded checklist

#### Scenario: Requirements render in sequence order
- **WHEN** a resolve response has requirements with different `sequence`
  values
- **THEN** they render in ascending `sequence` order

#### Scenario: Prerequisites are visually distinct from documents
- **WHEN** a resolve response includes both `kind: "prerequisite"` and
  `kind: "document"` requirements
- **THEN** the two kinds are visually distinguishable on the plan screen

### Requirement: Requirement resources render as tappable downloads
When a requirement's `resources` array is non-empty, the app SHALL
render each resource as a tappable link (label + type), opening its URL
when tapped — never a bare URL left in prose. When a requirement's own
detail text states a printing requirement (e.g. laser-print on A4), the
app SHALL render that note alongside the resource links.

#### Scenario: A domestic form renders its resource links
- **WHEN** a requirement's `resources` includes a domestic form PDF
- **THEN** it renders as a tappable link labeled with the resource's own
  `label`

#### Scenario: An overseas applicant sees the overseas form set, not the domestic one
- **WHEN** a case's resolved requirements are for an overseas applicant
- **THEN** the rendered resource links are the Overseas Missions form
  (and any applicable annexes) returned by the backend, not the
  domestic form

#### Scenario: The printing note renders when present
- **WHEN** a requirement's detail text includes an A4/laser-print
  instruction
- **THEN** that instruction is visible alongside its resource links, not
  only buried in unrendered text

### Requirement: Authorized studios render for the applicant's district
When the app has the citizen's answered district, it SHALL call
`GET /studios` for that district and render the returned studio list
(name, address, phone when present) alongside the plan, including the
standing receipt-submission note from the response.

#### Scenario: Studios render for a district with results
- **WHEN** `GET /studios` returns one or more studios for the citizen's
  district
- **THEN** each renders with its name and address, and the response's
  receipt note is visible

#### Scenario: An empty studio result does not look broken
- **WHEN** `GET /studios` returns an empty list for the citizen's
  district
- **THEN** the studio section shows an explicit empty state, not a
  blank gap or an error

### Requirement: A conflict note displays prominently
When a resolve response's `offices.conflict_note` is non-null, the app
SHALL display it prominently on the plan screen — not collapsed,
hidden, or requiring an extra tap to reveal.

#### Scenario: A present conflict note is visible without extra interaction
- **WHEN** `offices.conflict_note` is non-null
- **THEN** its text is visible on first render of the plan screen

### Requirement: An amendment alternative is presented as a real choice
When a resolve response's `amendment_alternative` is non-null, the app
SHALL present both the primary plan and the amendment alternative
side by side (or equally reachable without scrolling past a full
primary plan first), each with its own fee and requirements, so the
citizen can compare and decide — not buried below the main plan as an
afterthought.

#### Scenario: A name-change case shows both options
- **WHEN** `amendment_alternative` is non-null
- **THEN** the plan screen shows the primary plan's fee/requirements and
  the amendment alternative's fee/requirements as two comparable options

#### Scenario: No alternative means no extra section
- **WHEN** `amendment_alternative` is null
- **THEN** no alternative-choice section renders

### Requirement: A scope-gated case renders its refusal, never a partial plan
When a resolve response's `scope_gate` is non-null, the app SHALL render
`scope_gate.reason` as the plan screen's content and SHALL NOT render
any requirement, fee, or office section — since the resolve response
carries no plan data in this case (`fee`, `offices`, and `requirements`
are null/empty when `scope_gate` is set).

#### Scenario: A scope-gated response shows the reason, not a checklist
- **WHEN** `scope_gate` is non-null
- **THEN** the plan screen shows the reason text and no checklist,
  fee, or office section renders

#### Scenario: An empty checklist never reads as a complete plan
- **WHEN** `scope_gate` is non-null
- **THEN** nothing on the plan screen implies the citizen has a
  complete, ready-to-use plan

### Requirement: Every data surface handles all four states
Every screen or section that renders data from the API (services list,
chat, plan, studios) SHALL handle loading, empty, error, and loaded
states distinctly.

#### Scenario: Loading is visible before data arrives
- **WHEN** a request is in flight
- **THEN** a loading indicator is shown for that surface, not a blank
  screen

#### Scenario: An empty result is distinguished from a loading or error state
- **WHEN** a request succeeds with no data to show (e.g. no services, no
  studios for a district)
- **THEN** an explicit empty-state message renders, distinct from both
  the loading and error presentations

#### Scenario: An error state is distinguished from loading and empty
- **WHEN** a request fails
- **THEN** an error message with a retry affordance renders, and it is
  visually distinguishable from both the loading and empty states

### Requirement: A chat turn shows a thinking indicator while the backend responds
Because most chat turns call an LLM and take multiple seconds, the app
SHALL show a visible "thinking" indicator for the duration of a chat
turn's request, from send to response.

#### Scenario: A thinking indicator appears while a turn is in flight
- **WHEN** a chat message has been sent and the response has not yet
  arrived
- **THEN** a thinking indicator is visible for that duration

#### Scenario: The thinking indicator clears when the response arrives
- **WHEN** a chat turn's response arrives (success or error)
- **THEN** the thinking indicator is removed and replaced by the actual
  result

### Requirement: Network failure, an unreachable backend, and a server error each show a distinct message
The app SHALL distinguish, in the message shown to the citizen, between
a network failure (no connectivity), an unreachable backend (connection
refused/timeout to a reachable network), and a server error (a 5xx
response) — each with a distinct plain-language message and a retry
affordance. A generic "something went wrong" SHALL NOT be the only
message shown for any of these.

#### Scenario: No network connectivity
- **WHEN** a request fails because the device has no network connection
- **THEN** the shown message is specific to lacking connectivity, with a
  retry affordance

#### Scenario: Backend unreachable
- **WHEN** a request fails because the configured backend cannot be
  reached (but the device has network connectivity)
- **THEN** the shown message is specific to the backend being
  unreachable, with a retry affordance

#### Scenario: A 500 response
- **WHEN** a request receives a 5xx response
- **THEN** the shown message is specific to a server error, with a
  retry affordance, distinct from the network-failure and
  unreachable-backend messages
