## Purpose

Turns a citizen's free-text chat message into a routing decision — an
answer to record, a question to route to RAG, or both — without ever
producing a fee, office, or requirement itself. Sits between the chat
route and the rules engine / RAG layer.

## ADDED Requirements

### Requirement: Every message is truncated before any model call
Every citizen message SHALL be truncated to 2,000 characters before it
reaches the deterministic pass or any Claude API call.

#### Scenario: An over-length message is truncated
- **WHEN** a citizen message exceeds 2,000 characters
- **THEN** only the first 2,000 characters reach the deterministic pass
  and any subsequent Claude API call

### Requirement: A deterministic pass records an obvious answer without an API call
When a case has a pending question, and the message plausibly answers it
by type (a recognized district name where a district was asked, a
number where a numeric answer was expected, a yes/no term where a
boolean was asked), the system SHALL record it as the answer to that
question without calling the Claude API.

#### Scenario: A bare district name answers a pending district question
- **WHEN** the pending question expects a district and the message is
  exactly a recognized district name
- **THEN** the district is recorded as the answer, and no Claude API
  call is made

#### Scenario: A message with surrounding prose does not use the deterministic pass
- **WHEN** the message contains more than a bare type-appropriate answer
  (e.g. a full sentence around a number)
- **THEN** the deterministic pass does not match, and the message is
  classified via the Claude API instead

### Requirement: Ambiguous messages are classified via the Claude API
When the deterministic pass does not match, the system SHALL classify
the message via the Claude API into an `intent` (`situation`,
`question`, or `answer`), a set of `extracted` facts keyed by condition
attribute, and whether the message `contains_question`.

#### Scenario: A classification returns intent, extracted facts, and contains_question
- **WHEN** a message is classified via the Claude API
- **THEN** the result includes an `intent`, an `extracted` mapping (which
  may be empty), and a `contains_question` boolean

### Requirement: Low-confidence classification defaults to a question, not a silent fact
When classification confidence is low, the system SHALL treat the
message as `intent = question` and SHALL NOT record any fact against
the case's pending question.

#### Scenario: A low-confidence classification leaves the pending question open
- **WHEN** a message's classification confidence is low
- **THEN** the pending question remains unanswered, regardless of what
  the low-confidence classification extracted

### Requirement: A message can be both a situation and a question, handled in one turn
When a message both contains extractable facts and asks a question, the
system SHALL record the extracted facts and answer the question via RAG
in the same turn, rather than picking one.

#### Scenario: A combined message records the fact and answers the question
- **WHEN** a message states a fact relevant to the case and asks an open
  question in the same turn
- **THEN** the fact is recorded as a case answer, and the question is
  answered via RAG, in that same turn's response

### Requirement: The classifier never produces plan-shaped output
Classification SHALL NOT return a fee, an office, or a requirement —
those come only from the rules engine.

#### Scenario: A classification result carries no plan data
- **WHEN** a message is classified, regardless of its content
- **THEN** the classification result contains no fee, office, or
  requirement field
