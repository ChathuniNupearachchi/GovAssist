## Purpose

Fetches a page or PDF from the Immigration Department site and persists
it as an unmodified, hashed, timestamped snapshot before any parsing
touches it — the audit trail every later step (chunking, rule parsing,
review) depends on, and the reason change detection (a later phase) is
possible at all.

## ADDED Requirements

### Requirement: A fetch persists the raw snapshot before any parsing
Fetching a page or PDF SHALL save its raw, unmodified content as the
`SourceDocument`'s snapshot before any extraction or parsing is performed
on it. Parsing SHALL read from the saved snapshot, never from a
not-yet-persisted in-memory fetch result.

#### Scenario: A fetched page is snapshotted first
- **WHEN** the scraper fetches a page
- **THEN** the page's raw content is persisted as a `SourceDocument`
  snapshot before any HTML parsing is performed on it

#### Scenario: A fetched PDF is snapshotted first
- **WHEN** PDF extraction fetches a PDF
- **THEN** the PDF's raw bytes are persisted as a `SourceDocument`
  snapshot before any text extraction is performed on it

### Requirement: A snapshot's content hash is comparable across runs
Every snapshot SHALL be stored with a SHA-256 hash of its raw content, so
that fetching the same URL again can be compared against the previous
hash to detect whether the source changed.

#### Scenario: Re-fetching unchanged content produces the same hash
- **WHEN** the same URL is fetched twice with no change to its content in
  between
- **THEN** both fetches produce the same content hash

#### Scenario: Re-fetching changed content produces a different hash
- **WHEN** the same URL is fetched, its content changes, and it is fetched
  again
- **THEN** the second fetch's content hash differs from the first

### Requirement: Every fetched document records its source and fetch time
Every `SourceDocument` created by a fetch SHALL record the exact URL it
was fetched from and the timestamp it was fetched at.

#### Scenario: A fetched document is persisted
- **WHEN** a page or PDF is fetched
- **THEN** the resulting `SourceDocument` has a non-null `source_url` and
  `fetched_at`

### Requirement: Document type distinguishes pages from PDFs
Every `SourceDocument` created by this pipeline SHALL record its
`document_type` as `html` for scraped pages or `pdf` for extracted PDFs.

#### Scenario: A scraped page is typed html
- **WHEN** the scraper persists a fetched page
- **THEN** its `document_type` is `html`

#### Scenario: An extracted PDF is typed pdf
- **WHEN** PDF extraction persists a fetched PDF
- **THEN** its `document_type` is `pdf`

### Requirement: A newly fetched document is never live
Every `SourceDocument` created by a fetch SHALL start with `status`
`pending`. Fetching SHALL NOT set any other status.

#### Scenario: A freshly fetched document starts pending
- **WHEN** a page or PDF is fetched and persisted
- **THEN** its `status` is `pending`

### Requirement: Fetching is rate-limited and self-identifying
Requests to the source site SHALL be rate-limited rather than sent in an
unthrottled burst, and SHALL send a descriptive `User-Agent` identifying
the request as GovAssist's ingestion pipeline.

#### Scenario: Requests are throttled
- **WHEN** the pipeline fetches more than one URL in sequence
- **THEN** consecutive requests are separated by a rate limit delay, not
  sent back-to-back

#### Scenario: Requests identify their origin
- **WHEN** the pipeline sends a request to the source site
- **THEN** the request's `User-Agent` header identifies it as GovAssist's
  ingestion pipeline, not a generic or spoofed client identity
