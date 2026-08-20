# document-chunking Specification

## Purpose

Splits an ingested document's extracted text into passage-sized chunks
and embeds each one locally, so a later retrieval capability has
something to search — without depending on any reviewer-approval
workflow this phase does not build.

## Requirements

### Requirement: A document's text is split into passage-sized chunks
Extracted prose text SHALL be split into chunks of roughly 200 to 400
words each, preserving reading order within the source document. A
table or list block detected during extraction SHALL be kept as a
single chunk regardless of its word count and SHALL NOT be split across
chunks, spliced back into the document at the position it occupied in
the source.

#### Scenario: A page produces multiple ordered chunks
- **WHEN** a scraped page's extracted prose text is chunked
- **THEN** it produces more than one chunk, each within roughly 200 to
  400 words, in the same order the text appeared in the source

#### Scenario: A table or list is never split across chunks
- **WHEN** a source document contains a table or a list
- **THEN** its content appears in exactly one chunk, regardless of how
  many words it contains, and that chunk occupies the block's original
  position relative to the surrounding prose chunks

### Requirement: Tabular and list-shaped content is extracted as structured markdown, not flattened prose
Extracting a document's content SHALL detect tabular and list-shaped
structure and convert each detected instance to markdown that preserves
its rows/columns or its items (and nesting, for a nested list), rather
than flattening it to an undifferentiated sequence of words and numbers.
This includes literal `<table>` elements and `<ul>`/`<ol>` lists in HTML
sources, tables `pdfplumber.extract_tables()` detects in PDF sources,
and — because a source page may present genuinely tabular data (for
example, a set of "Label - Value" fee lines) without a literal `<table>`
element — any other structural shape a source document uses for the
same purpose. Which structural shapes a given source's markup requires
detecting is an extraction-code decision, not a spec-level one; the
requirement is that tabular/list-shaped content ends up structured,
regardless of the source markup that expressed it.

#### Scenario: A fee table's rows stay distinguishable
- **WHEN** a source document presents fee data in rows (whether marked
  up as a literal `<table>` or as another structure the source uses for
  the same purpose, such as label-value lines)
- **THEN** the resulting chunk's content is markdown in which each row's
  values remain associated with their meaning, rather than a flat
  sequence of numbers with no indication of which figure applies to
  which case

#### Scenario: A list is extracted alongside surrounding prose
- **WHEN** a source document contains both prose text and one or more
  lists or tables
- **THEN** the lists and tables are extracted as markdown separately
  from the prose text, and both are present in the document's chunks in
  their original reading order

### Requirement: Every chunk carries metadata identifying its document, section, and source
Every chunk SHALL carry metadata recording the title of the document it
came from, the nearest preceding section heading in the source (if any),
its content type (`prose`, `table`, or `list`), and the source document's
URL.

#### Scenario: A chunk's metadata is populated
- **WHEN** a chunk is created during re-chunking
- **THEN** its metadata includes a non-null document title, content
  type, and source URL, and a section heading when one precedes it in
  the source

### Requirement: Only the embedded representation carries the context header, not the stored chunk text
The text passed to the embedding model SHALL be prefixed with a compact
context header built from the chunk's metadata (document title, section
heading, source URL) followed by the chunk's content. The chunk's
stored, citizen-facing text SHALL remain the raw content only, without
that header.

#### Scenario: A citation shows clean content, not the embedding header
- **WHEN** a chunk is cited in a checklist item or a RAG answer
- **THEN** the text shown to the citizen is the chunk's raw content,
  with no "Document: / Section: / Source:" header prepended

#### Scenario: The embedded vector reflects the context header
- **WHEN** a chunk's embedding is computed
- **THEN** it is computed from the header-prefixed text, not from the
  stored chunk text alone

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
