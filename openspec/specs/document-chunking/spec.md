# document-chunking Specification

## Purpose

Splits an ingested document's extracted text into passage-sized chunks
and embeds each one locally, so a later retrieval capability has
something to search — without depending on any reviewer-approval
workflow this phase does not build.

## Requirements

### Requirement: A document's text is split into passage-sized chunks
Extracted text SHALL be split into chunks of roughly 200 to 400 words
each, preserving reading order within the source document.

#### Scenario: A page produces multiple ordered chunks
- **WHEN** a scraped page's extracted text is chunked
- **THEN** it produces more than one chunk, each within roughly 200 to
  400 words, in the same order the text appeared in the source

### Requirement: Every chunk traces back to its source document
Every chunk SHALL reference the `SourceDocument` it was extracted from.

#### Scenario: A chunk resolves back to its source
- **WHEN** a chunk produced by this pipeline is inspected
- **THEN** it references exactly one `SourceDocument`, and that document
  is the one its text was extracted from

### Requirement: Chunks are embedded locally, without a GPU
Every chunk SHALL be embedded into a 384-dimension vector using a
CPU-only local model, with no dependency on GPU hardware or an external
embedding API.

#### Scenario: A chunk has a 384-dimension embedding
- **WHEN** a chunk is created
- **THEN** it has an `embedding` of exactly 384 dimensions, computed
  without calling an external service

### Requirement: Embedded chunks support similarity search
The stored embeddings SHALL support a similarity query that returns the
chunks most relevant to a given query text, ranked by similarity.

#### Scenario: A similarity query returns relevant chunks
- **WHEN** a query embedding is compared against the stored chunk
  embeddings for a document that is topically relevant to the query
- **THEN** the chunks returned are ones a human would judge relevant to
  the query, ranked with the most relevant first

### Requirement: PDF text extraction falls back to the Claude API when no text layer exists
When a PDF's text layer yields no usable text (a scanned document), the
system SHALL extract its text via the Claude API instead of failing or
silently producing an empty chunk set. Which method produced a document's
text SHALL be recorded.

#### Scenario: A scanned PDF still produces chunks
- **WHEN** a PDF's text layer contains no extractable text
- **THEN** the system extracts its text via the Claude API and proceeds
  to chunk and embed it like any other document

#### Scenario: A text-layer PDF does not invoke the Claude API
- **WHEN** a PDF's text layer already yields usable text
- **THEN** extraction uses that text layer directly, without calling the
  Claude API

#### Scenario: Extraction method is recorded
- **WHEN** a document's text has been extracted
- **THEN** which method produced it (text layer vs Claude API) is
  recorded and inspectable

### Requirement: Chunking does not depend on reviewer approval
This phase builds no reviewer-approval workflow. Chunking and embedding
SHALL run on ingested documents regardless of their `pending` status —
restricting retrieval to `approved` documents is a later capability's
responsibility, not this pipeline's.

#### Scenario: A pending document can still be chunked
- **WHEN** a `SourceDocument` with `status` `pending` has been ingested
- **THEN** it can still be chunked and embedded by this pipeline

### Requirement: HTML text extraction excludes navigation and footer boilerplate
Extracting text from an `html` `SourceDocument` SHALL exclude the page's
navigation menu and footer/quick-links boilerplate before the text is
split into chunks, so that boilerplate identical across every page does
not consume chunk budget or dilute a chunk's embedding.

#### Scenario: A chunk never consists mainly of navigation links
- **WHEN** an HTML page's text is extracted and chunked
- **THEN** no resulting chunk consists mainly of navigation menu items or
  footer quick-links/related-links/contact text

#### Scenario: Content-bearing text is preserved
- **WHEN** boilerplate is excluded from an HTML page's extracted text
- **THEN** every citizen-relevant sentence that was present in the page's
  main content is still present in the extracted text
