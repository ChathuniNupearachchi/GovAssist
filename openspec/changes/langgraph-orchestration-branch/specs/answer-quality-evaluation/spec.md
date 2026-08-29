## Purpose

Grows and quantifies the project's evaluation coverage beyond the
original ten-scenario golden set, and turns that coverage into an
automated CI gate, so a regression in resolved-plan correctness or
answer quality is caught before merge, not discovered by a citizen.

## ADDED Requirements

### Requirement: The golden set covers at least 25 hand-verified scenarios across four categories
The golden set SHALL contain at least 25 (and no more than 30)
hand-verified scenarios, covering renewal branches, general open
questions, exact-identifier queries, and out-of-corpus queries that must
be refused, each with a hand-verified expected outcome.

#### Scenario: Every required category is represented
- **WHEN** the golden set is inspected
- **THEN** it contains at least one scenario in each of: a renewal
  branch, a general open question, an exact-identifier query, and an
  out-of-corpus refusal

#### Scenario: An out-of-corpus scenario expects a refusal
- **WHEN** an out-of-corpus golden scenario is run
- **THEN** its expected outcome is the explicit no-relevant-match
  response, not a fabricated answer

### Requirement: RAGAS metrics are computed against the golden set
The system SHALL compute context precision, context recall,
faithfulness, and answer relevancy against the golden set, and record
the resulting scores as a baseline.

#### Scenario: All four RAGAS metrics are recorded
- **WHEN** a RAGAS evaluation run completes against the golden set
- **THEN** context precision, context recall, faithfulness, and answer
  relevancy scores are all recorded, not a subset

### Requirement: CI fails the merge on a golden scenario regression
Continuous integration SHALL run the golden scenario suite on every
change proposed for merge, and SHALL fail the build when any golden
scenario's actual outcome no longer matches its hand-verified expected
outcome.

#### Scenario: A regressed scenario blocks the merge
- **WHEN** a proposed change causes a previously passing golden scenario
  to produce a different outcome than its expected one
- **THEN** the CI run for that change fails

#### Scenario: External-API tests are marked, skipped, and reported
- **WHEN** CI runs a test that depends on a live external API call
- **THEN** that test is marked as external-API, skipped in the CI run,
  and its skip is reported in the run's output rather than silently
  omitted
