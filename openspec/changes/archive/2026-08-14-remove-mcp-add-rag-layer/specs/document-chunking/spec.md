## Purpose

Turns an approved source document into retrievable passages with local
embeddings, so open-ended citizen questions can be answered by retrieval
instead of the rules engine, while still tracing every passage back to a
dated, sourced document.

## ADDED Requirements

### Requirement: Approved documents are split into retrievable chunks
The system SHALL split a source document's content into passage-sized
chunks suitable for retrieval once that document is approved.

#### Scenario: An approved document produces chunks
- **WHEN** a source document's status is "approved"
- **THEN** the system produces one or more chunks from its content

#### Scenario: A pending or rejected document produces no chunks
- **WHEN** a source document's status is "pending" or "rejected"
- **THEN** the system does not chunk or embed its content

### Requirement: Chunks are embedded locally and stored in pgvector
Every chunk SHALL have a vector embedding computed by a local,
CPU-only embedding model and persisted in pgvector, so retrieval can run
without a network call to an external embedding service.

#### Scenario: A chunk has a stored embedding
- **WHEN** a chunk is created
- **THEN** it has a corresponding vector embedding stored in pgvector

### Requirement: Every chunk traces back to its source document
Every chunk SHALL reference the `SourceDocument` it was extracted from, so
a retrieved chunk can be cited with the same source and verified-as-of date
shown on checklist items.

#### Scenario: A chunk's citation matches its source
- **WHEN** a chunk is retrieved
- **THEN** its source document and verified-as-of date can be resolved
  from the chunk's stored reference

### Requirement: Approving a document re-embeds its chunks
When a previously-approved document's content changes and is re-approved,
the system SHALL re-chunk and re-embed it so retrieval never serves chunks
from a stale version.

#### Scenario: Re-approval refreshes chunks
- **WHEN** an already-approved source document is updated and re-approved
- **THEN** its existing chunks are replaced with chunks reflecting the new
  content