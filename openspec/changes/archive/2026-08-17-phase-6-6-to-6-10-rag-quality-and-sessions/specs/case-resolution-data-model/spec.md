## MODIFIED Requirements

### Requirement: Source document chunks are persisted with a vector embedding
Every chunk SHALL reference the source document it was extracted from,
carry its text and a sequence position within that document, store a
384-dimension vector embedding suitable for pgvector similarity search,
and carry a `metadata` JSONB column recording its document title,
nearest preceding section heading, content type (`prose`, `table`, or
`list`), and source URL. The chunk's text SHALL also support full-text
search independent of its vector embedding.

#### Scenario: A chunk is persisted
- **WHEN** a chunk is created
- **THEN** it references exactly one source document, and has non-null
  `chunk_text`, `sequence`, `embedding`, and `metadata`

#### Scenario: Chunk embedding dimension is fixed
- **WHEN** a chunk's embedding column is inspected
- **THEN** it is a vector of exactly 384 dimensions

#### Scenario: A chunk's text is searchable by exact term
- **WHEN** a chunk's `chunk_text` contains a specific term or identifier
- **THEN** a full-text search for that term can find the chunk,
  independent of its vector embedding's similarity score

## ADDED Requirements

### Requirement: Chat messages are persisted per case
Every chat message, in either direction, SHALL be persisted with a
reference to exactly one case, a role (`user` or `assistant`), its
content, when it was created, an optional intent classification, and an
optional list of cited chunk ids — forming the durable record of what a
citizen was actually told.

#### Scenario: A chat message is persisted
- **WHEN** a chat message is created
- **THEN** it references exactly one case, and has a non-null `role`,
  `content`, and `created_at`

#### Scenario: An assistant message records what it cited
- **WHEN** an assistant message answers from retrieved chunks
- **THEN** its `cited_chunk_ids` records which chunks were cited

#### Scenario: A user message may carry no citations
- **WHEN** a user message is persisted
- **THEN** its `cited_chunk_ids` may be null, since a citizen's message
  cites nothing
