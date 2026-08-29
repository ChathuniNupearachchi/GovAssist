## Purpose

Makes the intake conversation read as a conversation rather than a form
— the surface wording of a question adapts to what the citizen just
said, and a recorded fact is acknowledged before the next question — all
without moving which question gets asked, or what a fee/office/
requirement is, off the deterministic rules engine.

## Requirements

### Requirement: A question's surface wording may be rephrased; which question is asked never is
The next pending question presented to a citizen MAY be rephrased from
its canonical prompt for conversational fit, using the canonical prompt,
recent conversation context, and the attribute it asks about as input.
Which attribute is asked next SHALL always be the one the deterministic
next-question selection produces — rephrasing never changes, reorders,
or skips a question.

#### Scenario: A rephrased question still asks about the correct attribute
- **WHEN** the next pending question is rephrased
- **THEN** the rephrased text asks about the same attribute the
  canonical prompt asks about, and an answer to it is recorded against
  that attribute

#### Scenario: The canonical prompt is what gets logged and tested
- **WHEN** a rephrased question is presented to a citizen
- **THEN** the case's pending-question state and any recorded log still
  reference the canonical prompt, not the rephrased text

### Requirement: A rephrasing that drifts to the wrong attribute falls back to canonical
Rephrasing SHALL report which attribute it believes its rephrased text
asks about. When that reported attribute does not match the attribute
the canonical prompt actually asks about, the canonical prompt SHALL be
shown instead of the rephrased text.

#### Scenario: A mismatched rephrasing is discarded
- **WHEN** a rephrasing's reported attribute does not match the pending
  question's actual attribute
- **THEN** the citizen sees the canonical prompt, not the rephrased text

### Requirement: A rephrasing failure falls back to the canonical prompt
When rephrasing does not complete successfully (an API error, a timeout,
or any other generation failure), the canonical prompt SHALL be shown
instead, with no error surfaced to the citizen.

#### Scenario: An API failure during rephrasing still produces a question
- **WHEN** the rephrasing call fails
- **THEN** the citizen is shown the canonical prompt, and no error is
  visible to them

### Requirement: A recorded fact is acknowledged before the next question
When a chat turn records one or more facts to the case, the response
SHALL acknowledge exactly those recorded facts, and no others. An
acknowledgement SHALL NOT state a fact that was not actually recorded
during that turn.

#### Scenario: An acknowledgement matches what was actually recorded
- **WHEN** a turn extracts and records a fact
- **THEN** the response acknowledges that fact, and does not acknowledge
  any fact the turn did not record

#### Scenario: No fact recorded means no acknowledgement
- **WHEN** a turn records no new fact (for example, it only asks a
  question)
- **THEN** the response contains no fact acknowledgement

### Requirement: A newly triggered requirement is named in the acknowledgement, computed by the engine
When a recorded fact causes the rules engine to newly include a
requirement that was not applicable before that fact was recorded, the
acknowledgement SHALL name that requirement. Which requirement became
newly applicable SHALL be determined by the rules engine's own resolved-
requirement output before and after the fact was recorded, not asserted
by the model.

#### Scenario: A name change acknowledgement names the marriage certificate
- **WHEN** a citizen states their name changed after marriage, and the
  rules engine's requirement set gains the marriage certificate
  requirement as a result
- **THEN** the acknowledgement names the marriage certificate
  requirement

#### Scenario: An acknowledgement never names a requirement the engine didn't add
- **WHEN** a recorded fact does not change the engine's resolved
  requirement set
- **THEN** the acknowledgement does not claim any requirement was added

### Requirement: An acknowledgement never states a fee or office
An acknowledgement of a recorded fact SHALL NOT state a fee amount or an
office — those values come only from a tool result (see
`agentic-tool-answering`), never from an acknowledgement.

#### Scenario: An acknowledgement contains no fee or office
- **WHEN** an acknowledgement is generated
- **THEN** it contains no fee amount and no office name
