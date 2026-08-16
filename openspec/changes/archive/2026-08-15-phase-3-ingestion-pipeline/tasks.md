## 1. Scraper (`api/app/scraper/`)

- [x] 1.1 Define the five target URLs as config constants:
      `https://www.immigration.gov.lk/pages_e.php?id=7`,
      `https://www.immigration.gov.lk/pages_e.php?id=8`,
      `https://www.immigration.gov.lk/pages_e.php?id=9`,
      `https://www.immigration.gov.lk/pages_e.php?id=10`, and
      `https://www.immigration.gov.lk/studio_e.php`
- [x] 1.2 Implement an httpx fetch with a descriptive `User-Agent` header
      and a fixed delay between requests (rate limiting)
- [x] 1.3 Compute a SHA-256 hash of the raw fetched bytes
- [x] 1.4 Save the raw fetched bytes to
      `api/data/snapshots/{content_hash}.html`
- [x] 1.5 Persist a `SourceDocument` row: `source_url`, `snapshot_path`,
      `content_hash`, `document_type="html"`, `fetched_at`,
      `status="pending"`
- [x] 1.6 Confirm BeautifulSoup can parse the saved snapshot (read from
      disk, not from the in-memory fetch response) for the chunking step
      to use later

## 2. PDF extraction (`api/app/ingestion/`)

- [x] 2.1 Define the three target PDF URLs as config constants:
      `https://www.immigration.gov.lk/content/files/applications/instructions_english_td.pdf`,
      `https://www.immigration.gov.lk/content/files/applications/passport_application.pdf`,
      and
      `https://www.immigration.gov.lk/content/files/applications/amendment.pdf`
- [x] 2.2 Reuse the scraper's rate-limited, User-Agent-identified fetch for
      PDF downloads
- [x] 2.3 Compute a SHA-256 hash of the raw fetched PDF bytes
- [x] 2.4 Save the raw fetched bytes to
      `api/data/snapshots/{content_hash}.pdf`
- [x] 2.5 Persist a `SourceDocument` row per PDF: `source_url`,
      `snapshot_path`, `content_hash`, `document_type="pdf"`,
      `fetched_at`, `status="pending"`
- [x] 2.6 Implement text extraction from a saved PDF snapshot using
      pdfplumber (concatenate text across all pages)
- [x] 2.7 Implement a Claude API fallback: when pdfplumber's extraction
      for a PDF yields no usable text (confirmed for
      `instructions_english_td.pdf` — a scanned document, 0 extractable
      characters), send the PDF to the Claude API and use its response as
      the extracted text instead
- [x] 2.8 Cache extraction method + result per content hash in
      `api/data/snapshots/{content_hash}.extraction.json`
      (`{"method", "text", "model", "extracted_at"}`); check this cache
      before re-running pdfplumber or re-calling the Claude API for a
      content hash already extracted
- [x] 2.9 Update CLAUDE.md's "How the Claude API is used" section to add
      this as a fourth narrow job (done — see this session's edit to
      CLAUDE.md)

## 3. Chunking (`api/app/ingestion/`)

- [x] 3.1 Implement an HTML-to-text function: read an html
      `SourceDocument`'s snapshot from disk, extract visible text via
      BeautifulSoup
- [x] 3.2 Implement a word-count-based chunking function: split text into
      ~200–400 word passages, preferring paragraph boundaries over hard
      mid-sentence cuts
- [x] 3.3 Implement "chunk a source document": given a `SourceDocument`,
      extract its text (HTML or PDF path per `document_type`), chunk it,
      and persist `DocumentChunk` rows (`source_document_id`,
      `chunk_text`, `sequence`) — no embedding yet
- [x] 3.4 Run chunking against each scraped page and confirm it produces
      more than one chunk, in source order

## 4. Embedding (`api/app/ingestion/`)

- [x] 4.1 Load `sentence-transformers`'s `all-MiniLM-L6-v2` model once
      (not per-chunk)
- [x] 4.2 Implement "embed a chunk": compute its 384-dimension vector and
      write it to `DocumentChunk.embedding`
- [x] 4.3 Run embedding against every chunk produced in section 3 and
      confirm each has a non-null 384-dimension `embedding`

## 5. Verification (Done-when criteria)

- [x] 5.1 Run the scraper against each of the five live target pages
      twice; confirm each resulting snapshot is retrievable. Hash
      determinism verified in isolation (identical bytes → identical
      SHA-256, confirmed directly); the live pages' hashes did NOT match
      across runs — each page embeds a live visitor counter that changes
      on every fetch (confirmed by diffing two fetches of `id=7`: the
      32,386-byte page was identical except for the counter digits). This
      is a real site characteristic, not a pipeline defect — see
      design.md's Risks section. Accepted as a known limitation; flagged
      as a real constraint for Phase 3.6 (change detection)
- [x] 5.2 Confirm PDF extraction produces non-empty extracted text for
      all three target instruction PDFs
- [x] 5.3 Confirm each scraped page produces multiple `DocumentChunk`
      rows, each resolving back to that page's `SourceDocument` via
      `source_document_id`
- [x] 5.4 Run a pgvector cosine-distance similarity query (e.g. embed the
      text "how do I renew my passport" and query against the stored
      chunk embeddings) and confirm the top results are chunks a human
      would judge relevant to passport renewal. Repeat with a query
      relevant to the amendment content (e.g. "change my name on my
      passport after marriage") and confirm it surfaces `id=10`'s
      amendment fee/timeline chunks, not just renewal chunks
- [x] 5.5 Inspect the chunks produced from `studio_e.php`: confirm
      whether they contain real studio entries (name/address/district) or
      only the page shell (dropdown, empty table headers). Record the
      outcome in the implementation notes rather than treating either
      result as a silent pass — this phase's Done-when criteria don't
      require real studio data, but the gap must be visible, not hidden
- [x] 5.6 Confirm under-16 content is present and retrievable: run a
      similarity query for "passport for a child under 16" against the
      chunks from the instructions PDF (`instructions_english_td.pdf`,
      section (c)) and from `pages_e.php?id=8`, and confirm the returned
      chunks cover parental consent, guardian requirements, and the
      3-year validity period for minors — not just adult renewal content.
      This must be verified directly, not assumed: Phase 4 will rely on
      this content existing before it can even return a correct
      "not yet covered" response for under-16 applicants
