## Why

Mentor review concluded the planned MCP server layer adds a hop with no
payoff — no external client calls GovAssist's tools, so FastAPI can call
the rules engine directly. Separately, CLAUDE.md's "Two kinds of question,
two mechanisms" split needs its RAG half actually built: open questions
("What's the process for a lost passport?") are not situation resolutions
and should never touch the rules engine. Today there is no retrieval path
for them at all. This change removes the never-built MCP layer from the
architecture and builds the missing RAG half: chunking, local embedding,
pgvector storage, and a grounded retrieval endpoint.

## What Changes

- Drop MCP server work from the architecture. No MCP code exists yet (per
  the prior `setup-fastapi-backend` change), so this is a scope removal,
  not a code deletion — no future change should plan MCP tools. FastAPI
  calls the rules engine directly, per CLAUDE.md's "Explicitly not used"
  section. Not marked breaking: nothing was ever built against it.
- Add a chunking step to the ingestion pipeline: approved scraped pages and
  PDFs are split into retrievable passages.
- Chunks are embedded locally with sentence-transformers (CPU-only) and
  stored in pgvector.
- Every chunk carries a foreign key to its source `SourceDocument`, so a
  retrieved chunk's citation and verified-as-of date always trace back to
  the same record checklist items cite.
- Retrieval only searches chunks belonging to `approved` source documents —
  `pending`/`rejected` documents are never retrievable, matching the
  checklist's existing "nothing ungrounded reaches a citizen" rule.
- Add a retrieval endpoint that returns a grounded answer with its
  supporting chunk citations, or an explicit "nothing relevant found"
  response instead of guessing.

## Capabilities

### New Capabilities
- `document-chunking`: splitting an approved source document into passages,
  embedding them locally, and persisting them in pgvector with a foreign
  key back to their source document.
- `rag-retrieval`: answering an open-ended question by retrieving relevant
  chunks (approved-only) and returning a grounded, cited answer — or an
  explicit no-match response when nothing relevant exists.

### Modified Capabilities
(none — no MCP-related spec exists yet to modify or remove; MCP was
architecture-level planning that never reached a spec delta. The rules
engine's own spec is unaffected: this change only removes an unused calling
layer in front of it and adds a separate, parallel retrieval path.)

## Impact

- New directory: `api/app/rag/` (chunk retrieval, grounded answer
  assembly) and chunking logic added to `api/app/ingestion/`, per
  CLAUDE.md's project structure.
- New pgvector-backed table for chunk embeddings, foreign-keyed to
  `source_documents` (from the `setup-fastapi-backend` change).
- New dependency: `sentence-transformers` (CPU-only local embeddings).
- New FastAPI route: retrieval/answer endpoint, rate-limited per CLAUDE.md's
  "All endpoints that call the LLM are rate-limited" rule (the answer
  generation step calls the Claude API).
- No change to the rules engine itself or to the mobile app's plan
  generation flow — case resolution keeps going through the rules engine,
  unchanged.
- No MCP code to remove from `api/`, since none was ever built — this is a
  documentation/architecture correction, already reflected in the current
  CLAUDE.md's "Explicitly not used" section.
