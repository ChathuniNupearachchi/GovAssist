## MODIFIED Requirements

### Requirement: Services and their source documents are persisted
The system SHALL persist a catalogue of services (each with a code, name,
and category) and, independently, a record of every scraped source
document (its URL, a local snapshot path, a content hash, its document
type, when it was fetched, its review status, and — once approved — the
date it was approved), so rule versions and RAG answers can later cite
which document justified them and as of when.

#### Scenario: A service is persisted
- **WHEN** a service is created
- **THEN** it has a non-null `code`, `name`, and `category`

#### Scenario: A source document is persisted
- **WHEN** a source document is created
- **THEN** it has a non-null `source_url`, `content_hash`,
  `document_type`, and `fetched_at`, and a `status`

#### Scenario: An approved source document records when it was approved
- **WHEN** a source document's `status` is set to `approved`
- **THEN** its `approved_at` is non-null, recording when that approval
  happened
