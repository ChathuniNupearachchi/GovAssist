## 1. Architecture cleanup

- [ ] 1.1 Confirm no MCP server code, dependency, or route exists anywhere
      under `api/` (there shouldn't be any yet); remove it if found
- [ ] 1.2 Confirm CLAUDE.md's "Explicitly not used → MCP server" section
      and "FastAPI calls the rules engine directly" already reflect this —
      no further doc change needed

## 2. Dependencies

- [ ] 2.1 Add `sentence-transformers` and `pgvector` (Python package) to
      `api/requirements.txt`, pinned
- [ ] 2.2 Install into `api/venv` and confirm a clean install

## 3. Chunk model and migration

- [ ] 3.1 Add a `Chunk` model to `api/app/models.py`: UUID primary key,
      `source_document_id` (foreign key to `source_documents`, not null),
      `content` (Text, not null), `embedding` (pgvector `Vector`, dimensioned
      to the chosen embedding model's output size), `chunk_index` (Integer,
      for stable ordering within a document)
- [ ] 3.2 Enable the pgvector extension in the target database (if not
      already enabled by the `pgvector/pgvector:pg16` image)
- [ ] 3.3 Generate and review an Alembic migration creating the `chunks`
      table with its foreign key and a similarity-search index (HNSW or
      IVFFlat) on `embedding`
- [ ] 3.4 Run the migration against the local Docker Postgres and confirm
      the `chunks` table exists with the expected columns and index

## 4. Chunking + embedding pipeline (`api/app/ingestion/`)

- [ ] 4.1 Implement a chunking function: fixed-size chunks with overlap,
      taking a source document's `raw_content` and returning ordered text
      passages
- [ ] 4.2 Implement local embedding: load a small CPU sentence-transformers
      model once, embed a list of chunk texts, return vectors
- [ ] 4.3 Implement the "chunk and embed an approved document" pipeline
      step: given a `SourceDocument` with status `approved`, produce and
      persist its `Chunk` rows with embeddings
- [ ] 4.4 Implement re-approval replace: when an already-approved document
      is re-approved, delete its existing chunks and insert freshly
      chunked/embedded ones inside a single transaction
- [ ] 4.5 Confirm `pending` and `rejected` documents are never passed into
      the chunking step

## 5. Retrieval (`api/app/rag/`)

- [ ] 5.1 Implement a retrieval query: embed the incoming question, run a
      pgvector similarity search joined against `source_documents` filtered
      to `status = 'approved'`, return the top matches above a relevance
      threshold
- [ ] 5.2 Implement the "no relevant chunks" path: when nothing clears the
      relevance threshold, return an explicit no-match result rather than
      calling the answer-generation step
- [ ] 5.3 Implement grounded answer assembly: given the retrieved chunks,
      generate an answer via the Claude API constrained to those chunks,
      returning the answer text plus each cited chunk's source document and
      verified-as-of date
- [ ] 5.4 Confirm the retrieval/answer path never calls the rules engine and
      never returns a checklist, fee, or office routing

## 6. FastAPI route

- [ ] 6.1 Add a retrieval endpoint (e.g. `POST /rag/ask`) that accepts a
      free-text question and returns the grounded answer with citations, or
      the no-match response
- [ ] 6.2 Apply rate limiting to the new endpoint, consistent with
      CLAUDE.md's "All endpoints that call the LLM are rate-limited" rule

## 7. Verification (Done-when criteria)

- [ ] 7.1 Confirm the architecture (code + CLAUDE.md) has no MCP layer
- [ ] 7.2 Approve a test source document and confirm it produces embedded
      rows in the `chunks` table
- [ ] 7.3 Send a retrieval query matching approved content and confirm the
      response includes relevant chunks with correct source citations
- [ ] 7.4 Confirm a query matching only `pending`/`rejected` content returns
      the no-match response, not those chunks
- [ ] 7.5 Confirm an existing rules-engine situation-resolution path (e.g.
      the passport renewal scenario) still produces its checklist/fee/office
      output unchanged, with no dependency on the new RAG code