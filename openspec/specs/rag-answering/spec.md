# rag-answering Specification

## Purpose

Answers a citizen's open question about the rules by retrieving relevant
passages from approved source documents and generating a grounded,
cited answer — or explicitly declining rather than guessing when
nothing relevant is found. Never produces a plan, fee, office
determination, or checklist; those come from the rules engine only.

## Requirements

### Requirement: Retrieval is scoped strictly to approved source documents
Retrieving chunks for a query SHALL search only `DOCUMENT_CHUNK` rows
whose `SOURCE_DOCUMENT.status` is `approved`. A chunk belonging to a
`pending` or `rejected` source document SHALL never be returned,
regardless of its similarity to the query.

#### Scenario: A pending document's chunks are never retrieved
- **WHEN** retrieval runs for a query that would otherwise match a chunk
  belonging to a `pending` source document
- **THEN** that chunk is not included in the result

### Requirement: A weak match triggers one reformulation retry before giving up
After retrieving chunks for a query, the system SHALL assess whether the
top match is strong enough to answer from. When it is not, the system
SHALL reformulate the query once and retry retrieval. When the
reformulated retry is still weak, the system SHALL return an explicit
"no relevant match" result rather than proceeding to generation.

#### Scenario: A weak initial match is retried once
- **WHEN** the top retrieved chunk for a query is a weak match
- **THEN** the system retries retrieval once with a reformulated query
  before deciding there is no relevant match

#### Scenario: A still-weak retry yields no relevant match
- **WHEN** both the original query and its one reformulation retry
  produce only weak matches
- **THEN** retrieval reports no relevant match, and generation is not
  invoked

### Requirement: Generation answers only from retrieved chunks and always cites them
Grounded generation SHALL produce an answer using only the retrieved
chunks' content, and SHALL cite the specific chunks the answer was built
from. Generation SHALL NOT be invoked when retrieval found no relevant
match. Every citation the model returns SHALL be verified to reference a
chunk that was actually part of the retrieved set passed to the model;
an answer citing a chunk outside that set SHALL be rejected and
regenerated once with an explicit instruction to cite only the provided
chunks. An answer with no citations at all SHALL also be rejected, since
a grounded answer always has at least one citation. If the regenerated
answer still fails verification, the system SHALL return the same
explicit "no relevant match" response used when retrieval itself found
nothing relevant. This verification requirement applies to every
generated response drawing on retrieved chunks, including a response
composed from multiple tool results (for example, a `retrieve_documents`
tool result folded into a multi-step comparison) — not only a single-
shot generation call.

#### Scenario: An answer cites its source chunks
- **WHEN** generation produces an answer from a set of retrieved chunks
- **THEN** the answer identifies which chunks it was built from, and
  every cited chunk is a member of the retrieved set

#### Scenario: No relevant match means no generated answer
- **WHEN** retrieval reports no relevant match for a query
- **THEN** the system returns an explicit "I don't have that
  information" response, and generation is never invoked

#### Scenario: A fabricated citation is rejected and retried
- **WHEN** generation returns an answer citing a chunk id that was not
  part of the retrieved set passed to the model
- **THEN** the answer is rejected and generation is retried once with an
  explicit instruction to cite only the provided chunks

#### Scenario: A citation-less answer is rejected
- **WHEN** generation returns an answer with an empty citation list
- **THEN** the answer is treated as a failure, not returned to the
  citizen as-is

#### Scenario: A repeated verification failure falls back to no relevant match
- **WHEN** the retried generation also fails citation verification
- **THEN** the system returns the same explicit "no relevant match"
  response used when retrieval itself found nothing relevant

#### Scenario: A tool-composed answer's document citations are verified too
- **WHEN** a response is composed from one or more tool results and
  includes a `retrieve_documents` result among them
- **THEN** every document citation in that response is verified against
  the chunks `retrieve_documents` actually returned, using the same
  verify-reject-retry-fallback mechanism as a single-shot generated
  answer

### Requirement: Retrieval ranks candidates by a blend of vector similarity and full-text relevance
Retrieval SHALL rank candidate chunks using both semantic similarity
(vector search) and exact-term relevance (full-text search) against the
query, combined into a single ranking, rather than vector similarity
alone. Approval-only scoping and the weak-match reformulation-retry
behavior are unaffected by this change; only the ranking beneath them
changes.

#### Scenario: An exact identifier retrieves correctly via blended ranking
- **WHEN** a query names a specific identifier that appears verbatim in
  the corpus (for example, a form number or a section reference)
- **THEN** the chunk containing that identifier ranks as a top result,
  even when vector similarity alone would not have ranked it highly

#### Scenario: A genuinely covered query outranks an uncovered one
- **WHEN** a query about content the corpus actually covers is compared
  against a query about a topic the corpus does not cover
- **THEN** the covered query's top match is accepted as relevant and the
  uncovered query's top match is not, under the blended ranking's
  accept/reject threshold

### Requirement: Every answer's citation carries a source URL and a verified-as-of date
Every citation on a RAG answer (or on a "no relevant match" response,
where applicable) SHALL carry the source document's URL and its
`approved_at` date, in the same citation format used for checklist
items, so citations are consistent across both paths.

#### Scenario: A grounded answer includes source URL and verified date
- **WHEN** a grounded answer is returned
- **THEN** it includes, for each cited chunk, the source document's URL
  and its `approved_at` date

### Requirement: RAG never produces a plan, fee, office, or checklist
RAG answers open questions about the rules. It SHALL NOT produce a
resolved requirement set, a fee amount, an office determination, or a
checklist — those are produced only by the rules engine
(case-resolution-engine).

#### Scenario: A situation question is not answered by RAG
- **WHEN** a query describes a citizen's specific situation rather than
  asking an open question
- **THEN** RAG's output contains no requirement set, fee, office
  determination, or checklist
