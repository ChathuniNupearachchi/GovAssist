## MODIFIED Requirements

### Requirement: Source document chunks are persisted with a vector embedding
Every chunk SHALL reference the source document it was extracted from,
carry its text and a sequence position within that document, store a
vector embedding suitable for pgvector similarity search whose dimension
matches whatever embedding model `document-chunking` is currently
configured to use, and carry a `metadata` JSONB column recording its
document title, nearest preceding section heading, content type
(`prose`, `table`, or `list`), and source URL. The chunk's text SHALL
also support full-text search independent of its vector embedding.

#### Scenario: A chunk is persisted
- **WHEN** a chunk is created
- **THEN** it references exactly one source document, and has non-null
  `chunk_text`, `sequence`, `embedding`, and `metadata`

#### Scenario: Chunk embedding dimension is fixed
- **WHEN** a chunk's embedding column is inspected
- **THEN** it is a vector whose dimension matches the currently
  configured embedding model's output dimension, fixed and consistent
  across every stored chunk at any given time

#### Scenario: A chunk's text is searchable by exact term
- **WHEN** a chunk's `chunk_text` contains a specific term or identifier
- **THEN** a full-text search for that term can find the chunk,
  independent of its vector embedding's similarity score
