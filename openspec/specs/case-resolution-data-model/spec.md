# case-resolution-data-model Specification

## Purpose

Defines the persisted shape of a service's rules — their versioning and
approval trail, the requirements/conditions/fees they resolve to, the
intake questions that drive a conversation, a citizen's resolved case and
plan, and the retrievable chunks of the source documents those rules cite
— so every later phase (ingestion, rules engine, RAG, API routes) reads
and writes one agreed schema instead of each inventing its own.

## Requirements

### Requirement: Services and their source documents are persisted
The system SHALL persist a catalogue of services (each with a code, name,
and category) and, independently, a record of every scraped source
document (its URL, a local snapshot path, a content hash, its document
type, when it was fetched, and its review status), so rule versions can
later cite which document justified them.

#### Scenario: A service is persisted
- **WHEN** a service is created
- **THEN** it has a non-null `code`, `name`, and `category`

#### Scenario: A source document is persisted
- **WHEN** a source document is created
- **THEN** it has a non-null `source_url`, `content_hash`, `document_type`,
  and `fetched_at`, and a `status`

### Requirement: Rule versions trace a service to its approving source
Every rule version SHALL belong to exactly one service, reference the
source document that justified it, record who approved it and when, and
carry a version number and a status of `draft`, `approved`, or
`superseded` — so a citizen's plan can always be traced back to the
document and reviewer that made it valid.

#### Scenario: A rule version is persisted
- **WHEN** a rule version is created
- **THEN** it references exactly one service and one source document, and
  has a non-null `version_number` and `status`

#### Scenario: Rule version status is restricted
- **WHEN** a rule version's status is set
- **THEN** the value is one of `draft`, `approved`, or `superseded`

### Requirement: Requirements, conditions, and fees resolve per rule version
Every requirement, condition, and fee rule SHALL belong to exactly one
rule version. A requirement SHALL carry a label, a kind (`document`,
`step`, or `prerequisite`), an optional office it routes to, a freshness
rule, and a sequence position. A fee rule SHALL carry a base amount, an
optional penalty amount, and a basis (`normal` or `urgent`).

#### Scenario: A requirement is persisted
- **WHEN** a requirement is created
- **THEN** it references exactly one rule version, and has a non-null
  `label`, `kind`, and `sequence`

#### Scenario: Requirement kind is restricted
- **WHEN** a requirement's kind is set
- **THEN** the value is one of `document`, `step`, or `prerequisite`

#### Scenario: A fee rule is persisted
- **WHEN** a fee rule is created
- **THEN** it references exactly one rule version, and has a non-null
  `base_amount` and `basis`

### Requirement: A requirement gates on a flat set of independent conditions
Every condition SHALL reference the intake question it evaluates, an
attribute, an operator, and a comparison value. The operator SHALL be
restricted to exactly three values: `equals`, `lessThan`, or `in`.
Conditions do not nest, and a requirement's set of gating conditions is
not composed with AND/OR logic beyond "every linked condition must
hold" — `REQUIREMENT_CONDITION` links a requirement to zero or more
conditions, each optionally negated, and a requirement applies only when
every one of its linked conditions evaluates as expected.

#### Scenario: A condition's operator is restricted
- **WHEN** a condition's operator is set
- **THEN** the value is one of `equals`, `lessThan`, or `in`

#### Scenario: A condition cannot reference another condition
- **WHEN** the schema for a condition is inspected
- **THEN** it has no column or relationship that lets one condition point
  to another condition

#### Scenario: A requirement links to a flat set of conditions
- **WHEN** a requirement is linked to more than one condition via
  `REQUIREMENT_CONDITION`
- **THEN** every linked condition is evaluated independently, and each
  link can be negated on its own

### Requirement: Intake questions are persisted per service
Every question SHALL belong to exactly one service, carry a prompt, an
answer type (`single`, `boolean`, or `district`), and a sequence position,
so the chat intake can be driven by data rather than hardcoded flow.

#### Scenario: A question is persisted
- **WHEN** a question is created
- **THEN** it references exactly one service, and has a non-null `prompt`,
  `answer_type`, and `sequence`

#### Scenario: Question answer type is restricted
- **WHEN** a question's answer type is set
- **THEN** the value is one of `single`, `boolean`, or `district`

### Requirement: A citizen's case, answers, and resolved plan are persisted
Every case SHALL belong to exactly one service and record a device
reference, when it was resolved, and whether it is now outdated. Every
case answer SHALL belong to exactly one case and one question. Every plan
item SHALL belong to exactly one case, reference the requirement and rule
version it was resolved from, and record whether it has been collected
and its sequence position — so a saved plan stays traceable to the exact
rule version that produced it, even after that rule version is
superseded.

#### Scenario: A case answer is persisted
- **WHEN** a case answer is created
- **THEN** it references exactly one case and one question, and has a
  non-null `value`

#### Scenario: A plan item is persisted
- **WHEN** a plan item is created
- **THEN** it references exactly one case, one requirement, and the rule
  version that requirement came from, and has a non-null `sequence`

### Requirement: Source document chunks are persisted with a vector embedding
Every chunk SHALL reference the source document it was extracted from,
carry its text and a sequence position within that document, and store a
384-dimension vector embedding suitable for pgvector similarity search.

#### Scenario: A chunk is persisted
- **WHEN** a chunk is created
- **THEN** it references exactly one source document, and has non-null
  `chunk_text`, `sequence`, and `embedding`

#### Scenario: Chunk embedding dimension is fixed
- **WHEN** a chunk's embedding column is inspected
- **THEN** it is a vector of exactly 384 dimensions

### Requirement: Admin users are persisted with a review role
Every admin user SHALL carry an email and a role of either `reviewer` or
`approver`, so the (future) review console can distinguish who may draft
versus who may publish.

#### Scenario: An admin user is persisted
- **WHEN** an admin user is created
- **THEN** it has a non-null `email` and `role`

#### Scenario: Admin role is restricted
- **WHEN** an admin user's role is set
- **THEN** the value is one of `reviewer` or `approver`

### Requirement: The schema migration is reversible
The migration that creates this schema SHALL be reversible: rolling it
back SHALL remove exactly what it added, leaving no orphaned tables,
columns, or extensions.

#### Scenario: The migration rolls back cleanly
- **WHEN** the migration that creates this schema is rolled back one step
- **THEN** none of its 14 tables remain