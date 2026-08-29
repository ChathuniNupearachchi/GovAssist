## Purpose

Gives a reviewer a single operational-status landing view of what needs
their attention, without duplicating developer tooling that answers a
different question.

## ADDED Requirements

### Requirement: Home shows operational review status
The dashboard home SHALL show, computed from live and admin-owned data:
drafts pending review, sources not yet approved, services with no
approved rule version, and recently-approved items each with who
approved them and when.

#### Scenario: Counts reflect real state
- **WHEN** the dashboard home is loaded
- **THEN** each of the four sections shows counts and items computed
  from the actual current `ADMIN_DRAFT`/live `RULE_VERSION`,
  `SOURCE_DOCUMENT`, `SERVICE`, and `ADMIN_ACTION` data, not fixture or
  placeholder content

#### Scenario: Recently-approved items show attribution
- **WHEN** the dashboard home lists a recently-approved item
- **THEN** it shows which admin approved it and the timestamp, sourced
  from the corresponding `ADMIN_ACTION` row

### Requirement: No retrieval-quality or LLM-tracing views on this dashboard
The dashboard home SHALL NOT include a RAGAS retrieval-quality view or a
Langfuse LLM-tracing view. Both are developer tooling with their own
dedicated interfaces, and neither answers the reviewer's actual
question of whether a specific fee, document, or office is correct.

#### Scenario: Home stays scoped to review status
- **WHEN** the dashboard home is loaded
- **THEN** it contains only the four review-status sections and no
  embedded or linked-as-primary RAGAS or Langfuse panel
