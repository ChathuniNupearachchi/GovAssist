## Purpose

Defines the durable record of a scraped government-source document, so
later change-detection, human review, and rule-extraction work all have a
single, well-defined shape to read from and write to.

## ADDED Requirements

### Requirement: Source document records capture provenance
Every persisted source document SHALL record the URL it was fetched from, a
content hash of the fetched content, the raw fetched content, the document
type, and the timestamp it was fetched, so a later fetch of the same URL can
be compared against the stored hash to detect whether the source changed.

#### Scenario: Storing a fetched document
- **WHEN** a source document is persisted
- **THEN** it has a non-null `source_url`, a non-null `content_hash`, non-null
  `raw_content`, and a `fetched_at` timestamp

#### Scenario: Document type is recorded
- **WHEN** a source document is persisted without an explicit document type
- **THEN** its document type defaults to "html"

### Requirement: Source documents default to draft status
Scraped content SHALL NOT be treated as a verified source until a human
reviewer has approved it. Every source document SHALL default to "pending"
status when created, and its status SHALL only ever be one of "pending",
"approved", or "rejected".

#### Scenario: New document is not live by default
- **WHEN** a source document is created without specifying a status
- **THEN** its status is "pending"

#### Scenario: Status is restricted to known review states
- **WHEN** a source document's status is set
- **THEN** the value is one of "pending", "approved", or "rejected"
