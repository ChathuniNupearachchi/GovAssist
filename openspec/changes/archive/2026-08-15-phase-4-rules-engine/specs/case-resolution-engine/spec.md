## Purpose

Defines the behavior of the functions that resolve a citizen's answers
against the rule data into a condition result, a requirement set, a fee,
an office (with any conflict note), an ordered plan, and the next
question — built and unit-tested in isolation, with no API routes yet.

## ADDED Requirements

### Requirement: A condition evaluates against a case's answers
The condition evaluator SHALL evaluate a single condition against a
case's recorded answers using exactly the operator on that condition
(`equals`, `lessThan`, or `in`), and SHALL NOT nest or compose conditions
with AND/OR logic beyond what `REQUIREMENT_CONDITION`'s flat linkage
already expresses. When the relevant question has no recorded answer,
the condition SHALL evaluate as not satisfied rather than raising an
error.

#### Scenario: Each operator evaluates correctly
- **WHEN** a condition with operator `equals`, `lessThan`, or `in` is
  evaluated against a matching and a non-matching answer
- **THEN** it returns true for the matching answer and false for the
  non-matching one

#### Scenario: A missing answer evaluates as not satisfied
- **WHEN** a condition references a question the case has no answer for
- **THEN** the condition evaluates as not satisfied, and no error is
  raised

### Requirement: The requirement resolver returns only requirements whose conditions all pass
The requirement resolver SHALL return, for a given case, exactly the
requirements from the case's service's approved rule version whose
linked conditions (respecting each link's `negated` flag) all evaluate as
satisfied, ordered by `sequence`. For a dual-citizen case, the resolver
SHALL return the dual-citizen document set and SHALL NOT also return the
standard document set's requirements.

#### Scenario: Name change changes the returned set
- **WHEN** the resolver runs for a renewal case with a name change and,
  separately, for one without
- **THEN** the two calls return different requirement sets, and only the
  name-change case's set includes the marriage certificate requirement

#### Scenario: Dual citizen returns the dual-citizen set only
- **WHEN** the resolver runs for a dual-citizen renewal case
- **THEN** the returned set is exactly the dual-citizen document set,
  with no standard-set requirement present

#### Scenario: Section 19(2) flags the new-NIC prerequisite
- **WHEN** the resolver runs for a dual-citizen case whose answers
  indicate section 19(2) citizenship
- **THEN** the returned set includes the new-NIC prerequisite requirement

### Requirement: The fee calculator returns the fee for the case's basis
The fee calculator SHALL return the fee rule matching the case's service
and its urgent-or-normal answer, with its `base_amount` and citation.

#### Scenario: Both fee paths are covered
- **WHEN** the fee calculator runs for a normal-basis case and,
  separately, an urgent-basis case
- **THEN** it returns 10000.00 for normal and 20000.00 for urgent, each
  carrying `pages_e.php?id=8` as its citation

### Requirement: The office resolver is deterministic and never returns a Divisional Secretariat
The office resolver SHALL return the same set of accepting offices for
the same case inputs on every call (no randomness, no unordered-set
iteration exposed to callers), and SHALL NEVER include an office of
`type = ds` in its result. When the case's basis is urgent, the result
SHALL include the resolution note documenting the Regional Office
one-day-service conflict.

#### Scenario: Repeated calls return identical results
- **WHEN** the office resolver runs twice for the same case inputs
- **THEN** both calls return the same offices in the same order and the
  same conflict note presence

#### Scenario: Urgent service includes the conflict note
- **WHEN** the office resolver runs for a case with `basis = urgent`
- **THEN** its result includes the urgent-service resolution note

#### Scenario: A Divisional Secretariat is never returned
- **WHEN** the office resolver runs for any renewal case
- **THEN** no returned office has `type = ds`

### Requirement: The resolved plan is dependency-ordered, not a flat list
The resolver SHALL return plan items ordered such that the photo studio
acknowledgement prerequisite precedes every `document` requirement, a
section 19(2) new-NIC prerequisite precedes the application submission it
gates, and a fingerprints prerequisite (where applicable) is present as
an in-person step rather than a document to gather remotely.

#### Scenario: Studio acknowledgement is first
- **WHEN** a resolved plan is inspected in `sequence` order
- **THEN** the photo studio acknowledgement is the first item

### Requirement: Next-question logic returns the next unanswered question the resolver needs
Given a case's currently recorded answers, the next-question function
SHALL return the next `QUESTION` (by the service's question `sequence`)
that has no recorded answer yet and whose relevance is not already ruled
out by an answer already given, or SHALL return that no further question
is needed once every relevant question is answered.

#### Scenario: Answering a question changes what comes next
- **WHEN** the next-question function is called before and after the
  dual-citizen question is answered `false`
- **THEN** the two calls return different next questions (the
  section-19(2) follow-up is skipped once dual citizen is `false`)

### Requirement: An under-16 case is scope-gated, not resolved to a checklist
Age SHALL be evaluated first. When a case's age answer is under 16, the
resolver SHALL return an explicit "not yet supported" response directing
the citizen to the department, and SHALL NOT return the adult renewal
requirement set, fee, or plan.

#### Scenario: Under-16 returns the scope-gate response
- **WHEN** the resolver runs for a case whose age answer is under 16
- **THEN** it returns the scope-gate response and no plan items

### Requirement: A name change after marriage surfaces the amendment alternative
When a case's answers indicate the name changed after marriage, the
resolver SHALL return, alongside the renewal resolution, the amendment
service's fee, delivery time, and required documents as a surfaced
alternative — not silently assume renewal is the only option.

#### Scenario: Name change surfaces both options
- **WHEN** the resolver runs for a renewal case with a name change after
  marriage
- **THEN** its result includes both the renewal resolution and the
  amendment alternative (fee 1200.00, its own required documents)

### Requirement: Ten golden scenarios pass and regressions fail the build
A golden test set of the ten scenarios listed in `BACKEND_PLAN.md`
Phase 4.7, each with a hand-verified expected requirement set, fee,
office result, and (where applicable) scope-gate or amendment-alternative
output, SHALL run as part of the automated test suite and SHALL fail the
build if any scenario's actual output no longer matches its expected
output.

#### Scenario: The golden suite runs and can fail
- **WHEN** the automated test suite runs
- **THEN** all ten golden scenarios execute, and a deliberately
  introduced regression in any one of them fails the suite
