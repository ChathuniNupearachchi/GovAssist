## MODIFIED Requirements

### Requirement: A document's text is split into passage-sized chunks
Extracted prose text SHALL be split into chunks of roughly 200 to 400
words each, preserving reading order within the source document. A
table or list block detected during extraction SHALL be kept as a
single chunk regardless of its word count and SHALL NOT be split across
chunks, spliced back into the document at the position it occupied in
the source. A prose passage too short to stand alone as meaningful
content (for example, a bare trailing FAQ-style question immediately
preceding the list or table that answers it) SHALL be merged into the
block that immediately follows it, rather than becoming its own
near-content-free chunk, unless it is the last block in the document, in
which case it SHALL still be emitted rather than silently dropped.

#### Scenario: A page produces multiple ordered chunks
- **WHEN** a scraped page's extracted prose text is chunked
- **THEN** it produces more than one chunk, each within roughly 200 to
  400 words, in the same order the text appeared in the source

#### Scenario: A table or list is never split across chunks
- **WHEN** a source document contains a table or a list
- **THEN** its content appears in exactly one chunk, regardless of how
  many words it contains, and that chunk occupies the block's original
  position relative to the surrounding prose chunks

#### Scenario: A bare trailing question merges into its answering block
- **WHEN** a short prose passage (a bare question, for example) is
  immediately followed by the table or list block that answers it
- **THEN** the passage's text is merged into that following chunk rather
  than becoming its own standalone, near-content-free chunk

#### Scenario: A trailing fragment at the end of a document is not dropped
- **WHEN** a document ends on a prose passage too short to stand alone,
  with no following block to merge into
- **THEN** it is still emitted as its own chunk, not silently discarded

### Requirement: Chunks are embedded locally, without a GPU, by one consistently-used model
Every chunk SHALL be embedded using a single configured CPU-only local
embedding model, with no dependency on GPU hardware or an external
embedding API. The same configured model SHALL be used to embed both
stored chunks at ingestion time and queries at retrieval time — never a
mismatched pair. The embedding column's dimension SHALL match the
configured model's output dimension.

#### Scenario: A chunk's embedding matches the configured model's dimension
- **WHEN** a chunk is created
- **THEN** its `embedding` has exactly the dimension the currently
  configured embedding model produces, computed without calling an
  external service

#### Scenario: Ingestion and query time use the same model
- **WHEN** a query is embedded for retrieval
- **THEN** it is embedded with the same model, at the same dimension,
  that produced the stored chunk embeddings it is compared against

### Requirement: PDF text extraction uses the measured-best method per PDF, falling back to Claude vision for scans
Extracting a PDF's text SHALL use whichever method a recorded,
per-document measurement found superior for that specific PDF, defaulting
to the existing pipeline (pdfplumber's text layer, falling back to the
Claude API when no usable text layer exists) when no measured
alternative has been adopted for that document. Which method produced a
document's text SHALL be recorded. Adopting an alternative method for a
document SHALL NOT regress content only the previous method extracted —
in particular, a scanned PDF's Claude-vision-extracted content SHALL
remain retrievable after any extraction method change.

#### Scenario: A scanned PDF still produces chunks
- **WHEN** a PDF's text layer contains no extractable text and no
  measured alternative has been adopted for it
- **THEN** the system extracts its text via the Claude API and proceeds
  to chunk and embed it like any other document

#### Scenario: A text-layer PDF does not invoke the Claude API unnecessarily
- **WHEN** a PDF's text layer already yields usable text and no measured
  alternative has been adopted for it
- **THEN** extraction uses that text layer directly, without calling the
  Claude API

#### Scenario: Extraction method is recorded
- **WHEN** a document's text has been extracted
- **THEN** which method produced it is recorded and inspectable

#### Scenario: Adopting an alternative method preserves previously-extracted content
- **WHEN** an alternative extraction method is adopted for a document
  because a recorded measurement found it superior
- **THEN** every piece of content the previous method extracted remains
  present and retrievable after the switch — content the previous method
  alone captured is either present in the new method's output too, or
  the previous method is kept for that document instead of switching
