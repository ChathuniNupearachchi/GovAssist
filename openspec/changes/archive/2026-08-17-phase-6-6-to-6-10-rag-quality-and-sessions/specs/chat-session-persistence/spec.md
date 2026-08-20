## Purpose

Makes a citizen's conversation survive closing and reopening the app —
persisting every message as the durable audit trail, resolving a
returning device to its own case without an account, and keeping a fast
Redis-backed hot session in front of the Postgres record of truth.

## ADDED Requirements

### Requirement: A returning device resolves to its most recent unresolved case
Given a device reference, the system SHALL find that device's most
recent case that has not yet been resolved, if one exists, so a citizen
who closes and reopens the app continues the same case rather than
starting over. A device with no prior case SHALL start a new case
cleanly, with no error and no unrelated case attached.

#### Scenario: A returning device resumes its case
- **WHEN** a request arrives carrying a device reference that has an
  existing unresolved case
- **THEN** that case is resolved and reused, not recreated

#### Scenario: A new device starts cleanly
- **WHEN** a request arrives carrying a device reference with no prior
  case
- **THEN** a new case is created, and no prior, unrelated case is
  attached to it

#### Scenario: A resolved case is not resumed as if still in progress
- **WHEN** a device's only prior case has already been resolved
- **THEN** resuming that device does not treat the resolved case as
  still awaiting answers

### Requirement: Resuming a case restores both the next question and the prior conversation
Resuming an interrupted, unresolved case SHALL return both the correct
next pending question (per the existing engine state) and the case's
prior message transcript, so the citizen sees the conversation they left
rather than an engine that silently remembers facts behind an empty
chat.

#### Scenario: A mid-intake case resumes with context
- **WHEN** a case that was interrupted partway through intake is resumed
- **THEN** the response includes both the next unanswered question and
  the messages exchanged before the interruption

### Requirement: A device's active case transcript is retrievable on demand
A dedicated endpoint SHALL return the full, ordered message history for
a device's active case, so the app can restore the visible transcript
when it reopens.

#### Scenario: Reopening restores the visible transcript
- **WHEN** the app requests the transcript for a device with an active
  case
- **THEN** every message previously exchanged on that case is returned,
  in the order it occurred

### Requirement: Redis holds a fast-path hot session while Postgres remains the durable record
The active case's recent messages and answered facts SHALL be cached in
Redis with a bounded time-to-live, as a fast path. Postgres SHALL remain
the durable record such that clearing the Redis cache does not lose any
persisted message or fact — the transcript and case state remain fully
reconstructable from Postgres alone.

#### Scenario: Clearing the cache does not lose the transcript
- **WHEN** the Redis hot session for a case is cleared
- **THEN** requesting that case's transcript still returns the full,
  correct message history, reconstructed from Postgres
