## MODIFIED Requirements

### Requirement: Requirements, conditions, and fees resolve per rule version
Every requirement, condition, and fee rule SHALL belong to exactly one
rule version. A requirement SHALL carry a label, a kind (`document`,
`step`, or `prerequisite`), an optional office it routes to, a freshness
rule, a sequence position, and an optional `source_document_id` citing
the specific source document that fact came from. A fee rule SHALL carry
a base amount, an optional penalty amount, a basis (`normal` or
`urgent`), and an optional `source_document_id` citing the specific
source document that fee came from. A requirement's or fee rule's own
`source_document_id`, when present, is the citation shown to the
citizen; `RULE_VERSION.source_document_id` remains the version's primary
citation and is used only as a fallback when a requirement or fee rule
does not carry its own.

#### Scenario: A requirement is persisted
- **WHEN** a requirement is created
- **THEN** it references exactly one rule version, and has a non-null
  `label`, `kind`, and `sequence`

#### Scenario: Requirement kind is restricted
- **WHEN** a requirement's kind is set
- **THEN** the value is one of `document`, `step`, or `prerequisite`

#### Scenario: A requirement carries its own citation
- **WHEN** a requirement's facts come from a different document than its
  rule version's primary source
- **THEN** the requirement's own `source_document_id` references that
  document, independent of `RULE_VERSION.source_document_id`

#### Scenario: A fee rule is persisted
- **WHEN** a fee rule is created
- **THEN** it references exactly one rule version, and has a non-null
  `base_amount` and `basis`

#### Scenario: A fee rule carries its own citation
- **WHEN** a fee rule's amount comes from a different document than its
  rule version's primary source
- **THEN** the fee rule's own `source_document_id` references that
  document, independent of `RULE_VERSION.source_document_id`

### Requirement: The schema migration is reversible
The migration that creates this schema SHALL be reversible: rolling it
back SHALL remove exactly what it added, leaving no orphaned tables,
columns, or extensions.

#### Scenario: The migration rolls back cleanly
- **WHEN** the migration that creates this schema is rolled back one step
- **THEN** none of its 15 tables remain

## ADDED Requirements

### Requirement: Resolution notes attach advisory citations to a resolved case
The system SHALL persist advisory notes that are not a document, step, or
prerequisite a citizen collects, but change what the citizen should do
before acting on a resolution (for example, confirming an office accepts
a service before traveling there). Every resolution note SHALL carry its
note text and reference at least one source document; it MAY reference a
second source document when the advisory arises from two documents
disagreeing.

#### Scenario: A resolution note is persisted
- **WHEN** a resolution note is created
- **THEN** it has non-null `note_text` and references at least one
  source document

#### Scenario: A resolution note can cite two conflicting sources
- **WHEN** a resolution note documents a conflict between two published
  sources
- **THEN** it references both source documents, not just one
