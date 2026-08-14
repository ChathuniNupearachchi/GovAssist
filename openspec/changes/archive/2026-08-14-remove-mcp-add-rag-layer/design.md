## Context

See proposal.md - Why. The `setup-fastapi-backend` change (already planned,
not yet applied) established `SourceDocument` with a `pending` /
`approved` / `rejected` status and `api/app/scraper/`, `api/app/ingestion/`
as empty packages. This change builds on that model without modifying it:
chunks are a new table that references `SourceDocument` by foreign key.
CLAUDE.md's project structure names `api/app/rag/` for "chunk retrieval and
grounded answer generation" and folds chunking itself into
`api/app/ingestion/` — this design follows that split.

MCP removal has no code impact (see proposal.md - Impact): it only means no
future change plans an MCP tool layer. Nothing in this design touches it
further.

## Goals / Non-Goals

**Goals:**
- A chunking step that runs on approved documents and produces persisted,
  embedded chunks.
- A retrieval path that returns cited, grounded answers or an explicit
  "nothing relevant" response.
- Draft (pending/rejected) content is structurally unreachable by
  retrieval, not just filtered by convention.

**Non-Goals:**
- Building the rules engine (`api/app/engine/`) — out of scope, tracked by
  its own future change.
- Wiring chunking into the scraper's approval flow end-to-end (i.e. the
  human-review UI that flips a document to `approved`) — this change
  assumes that transition already happens and reacts to it; the reviewer
  workflow itself is a separate change.
- Choosing the final embedding model or similarity threshold values as
  permanent — reasonable defaults are chosen below and are cheap to tune
  later since they're config, not architecture.
- Rate limiting implementation details for the retrieval endpoint — the
  requirement (CLAUDE.md: "All endpoints that call the LLM are
  rate-limited") applies, but the specific limiter belongs with whatever
  the project already uses for the rest of the API, established when the
  first rate-limited endpoint is built.

## Decisions

**Chunk table lives in `api/app/models.py` alongside `SourceDocument`,
not a separate `rag` model module.** Keeps a single source of truth for
the schema Alembic autogenerates from, matching the existing pattern from
`setup-fastapi-backend`. The `api/app/rag/` package holds retrieval and
answer-generation *logic*, not the ORM model.
- Alternative: a `models/` package split by domain (as CLAUDE.md's
  long-term structure implies). Deferred until there are enough models to
  warrant the split, same reasoning as the prior change's design.md.

**Embedding column uses pgvector's `vector` type via `pgvector.sqlalchemy.Vector`**,
dimensioned to the chosen sentence-transformers model's output (384 for
the default `all-MiniLM-L6-v2` — small, CPU-fast, no GPU required, matching
CLAUDE.md's constraint). An HNSW or IVFFlat index is added on that column
so similarity search doesn't degrade to a full table scan as chunk volume
grows.
- Alternative: store embeddings as plain arrays/JSON and compute similarity
  in Python. Rejected — defeats the point of using pgvector, and won't
  scale past a handful of documents.

**Chunking is fixed-size with overlap (character or token count, not
semantic/sentence-boundary chunking) as the starting strategy** — simplest
to implement correctly and revisit. Chunk boundaries are an implementation
detail the spec deliberately doesn't pin down (spec only requires "one or
more chunks" per approved document).

**Re-approval replaces chunks rather than versioning them.** When a
document is re-approved after a content change, its old chunks for that
document are deleted and replaced with freshly chunked/embedded ones in the
same transaction as the re-embed step. Matches the "Approving a rule
version" consequence CLAUDE.md already lists ("re-embed affected chunks")
and keeps retrieval simple — always one current set of chunks per document,
no version resolution logic in the query path.
- Alternative: keep old chunks and mark them stale. Rejected for this
  change — adds query-time filtering complexity for a case (comparing
  chunk versions) nothing here needs yet.

**"Approved-only" is enforced with a SQL join filter on
`source_documents.status = 'approved'` in the retrieval query itself**,
not by only chunking approved documents and trusting that invariant to
hold forever. Belt-and-suspenders: even if a document is later demoted
from `approved` to `rejected` (e.g. a correction), its already-embedded
chunks stop being retrievable immediately without a separate cleanup step.
- Alternative: delete chunks the moment a document leaves `approved`
  status. Considered, but the join-filter approach gets the same
  citizen-facing guarantee (draft/rejected content is never retrievable)
  without needing that extra state-transition hook to be added and kept
  correct.

**Relevance threshold is a fixed, low-effort cosine-similarity cutoff for
this change**, not a learned or dynamic threshold. If nothing clears the
cutoff, the endpoint returns the explicit no-match response required by
the spec. The exact cutoff value is a tunable constant, not a design
commitment.

**No new capability for "generate the final grounded-answer text via
Claude API"** is added here beyond what `rag-retrieval`'s spec already
requires (answer must be grounded in retrieved chunks, cited, rate
limited). The three-narrow-jobs constraint on the Claude API already lives
in CLAUDE.md and doesn't need its own spec capability in this change.

## Risks / Trade-offs

- [Fixed-size chunking can split a requirement mid-sentence, weakening
  retrieval quality] → acceptable for a first pass; chunk strategy is
  swappable later without a spec change, since the spec only constrains
  outcomes (traceable, embedded, approved-only), not the chunking
  algorithm.
- [`all-MiniLM-L6-v2` (or similar small model) trades some retrieval
  quality for CPU-only speed] → matches CLAUDE.md's explicit "CPU only, no
  GPU needed" constraint; revisit only if retrieval quality proves
  insufficient in practice.
- [Re-approval replacing chunks means a brief window where a document has
  no chunks (delete-then-insert) if not wrapped tightly] → mitigated by
  doing the replace inside a single DB transaction, so retrieval never sees
  a document with zero chunks mid-update.
- [The join-filter approach means a chunk row can technically outlive its
  document's approval, sitting inert until a cleanup job removes it] →
  acceptable: it's unreachable by retrieval the moment status changes,
  which is the actual citizen-facing guarantee; storage cleanup is a
  housekeeping concern, not a correctness one.

## Migration Plan

1. Add the chunk table + pgvector column via Alembic migration (depends on
   `source_documents` existing from `setup-fastapi-backend`).
2. Add chunking + embedding logic to `api/app/ingestion/`.
3. Add retrieval + answer assembly logic to `api/app/rag/`.
4. Add the retrieval FastAPI route.
5. Backfill: run chunking against any already-approved documents once the
   pipeline exists (idempotent — re-running is the same as a re-approval
   replace).

No production data exists yet, so no live-traffic migration risk. Rollback
is an Alembic downgrade of the new chunk table.
