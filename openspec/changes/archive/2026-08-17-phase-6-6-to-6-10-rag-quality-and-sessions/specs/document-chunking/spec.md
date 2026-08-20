## MODIFIED Requirements

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

## ADDED Requirements

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
