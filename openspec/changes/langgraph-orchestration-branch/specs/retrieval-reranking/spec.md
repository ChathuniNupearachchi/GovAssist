## Purpose

Adds an optional second retrieval stage that rescores a wider candidate
pool against the query using a dedicated reranking model, so generation
can receive a narrower, better-ordered set of chunks than hybrid search
alone produces — measured against the existing calibration set, not
assumed, and shipped behind a configuration flag because that
measurement found the accept/reject benefit on this project's
calibration set to be zero while the latency cost was real (see
design.md's "Is reranking worth shipping" analysis).

## ADDED Requirements

### Requirement: Reranking is an optional stage, controlled by configuration, disabled by default
Whether retrieval reranks a candidate pool before generation SHALL be
controlled by a configuration setting, checked at query time. The
system SHALL ship with reranking disabled by default — enabling it is
an explicit operator choice, not the shipped behavior — based on a
measured finding that reranking changed zero accept/reject outcomes on
the project's calibration set (hybrid search alone already resolved all
of them) while adding materially to query latency.

#### Scenario: Reranking is off unless explicitly enabled
- **WHEN** the reranking configuration setting is left at its default
- **THEN** retrieval uses hybrid search's own ranking directly, with no
  reranking stage in the query path

#### Scenario: Reranking can be turned on by configuration
- **WHEN** the reranking configuration setting is explicitly enabled
- **THEN** retrieval fetches a wider candidate pool via the existing
  hybrid (vector + full-text + identifier) search than it passes to
  generation, scores every candidate in that pool against the query
  using a dedicated, self-hosted, CPU-only reranking model, and passes
  only the top-scoring subset to generation

#### Scenario: Reranking runs without a GPU or external API
- **WHEN** the reranking stage is enabled and scores a candidate pool
- **THEN** it does so using a locally loaded, CPU-only model, with no
  call to an external service

### Requirement: When enabled, the weak-match check requires both the pre-rerank hybrid signal and the reranker's own threshold to agree
When reranking is enabled, whether the top result is strong enough to
answer from SHALL require the pre-reranking hybrid accept rule (RRF
agreement, else cosine distance) to already accept, **and** the
reranker's own score to clear a threshold calibrated against the
reranker's score distribution on the calibration set. The reranker's
score alone SHALL NOT be sufficient to accept a result the pre-rerank
hybrid signal would have rejected — measured directly: the reranker
alone cannot separate this calibration set (a genuinely out-of-corpus
query scored higher than most in-corpus queries), while the pre-rerank
hybrid signal already separates all nine correctly on its own, with or
without reranking enabled.

#### Scenario: The accept/reject decision requires both signals to agree
- **WHEN** the weak-match check runs after reranking
- **THEN** a result is accepted only if the pre-rerank hybrid signal
  accepts it and the reranker's top score clears its own calibrated
  threshold

#### Scenario: A high reranker score cannot overrule a hybrid rejection
- **WHEN** the reranker assigns a high score to a result the pre-rerank
  hybrid signal would have rejected
- **THEN** that result is still rejected — the reranker score narrows
  and reorders candidates, it does not override the hybrid signal's
  accept/reject decision

### Requirement: Reranking's effect on the calibration set is measured in isolation
The calibration set SHALL be measured against the system both
immediately before and immediately after adding the reranking stage,
with every other component held constant, so reranking's own
contribution is distinguishable from any other change.

#### Scenario: A before/after pair isolates reranking's effect
- **WHEN** the reranking stage is added
- **THEN** the calibration set's results from immediately before and
  immediately after that addition are both recorded, with no other
  retrieval component changed between the two measurements

### Requirement: Whether reranking ships enabled is a measured decision, not an assumed default
Whether reranking runs by default SHALL be decided from a measured
comparison against the calibration set — the number of accept/reject
outcomes reranking changes versus hybrid search alone, and the query
latency reranking adds — recorded together, not from an assumption that
adding a reranking stage necessarily improves retrieval.

#### Scenario: A zero measured accept/reject improvement is recorded, not hidden
- **WHEN** reranking is measured against a calibration set hybrid search
  alone already resolves completely correctly
- **THEN** the recorded comparison states the measured accept/reject
  improvement is zero, rather than presenting reranking as an
  unqualified improvement

#### Scenario: The latency cost is recorded alongside the accept/reject comparison
- **WHEN** the decision to enable or disable reranking by default is
  made
- **THEN** the measured per-query latency reranking adds is recorded
  alongside the measured accept/reject comparison, so the decision
  reflects both, not the accept/reject result alone
