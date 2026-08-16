## Purpose

Answers a citizen's open question about the rules by retrieving relevant
passages from approved source documents and generating a grounded,
cited answer — or explicitly declining rather than guessing when
nothing relevant is found. Never produces a plan, fee, office
determination, or checklist; those come from the rules engine only.

## ADDED Requirements

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
match.

#### Scenario: An answer cites its source chunks
- **WHEN** generation produces an answer from a set of retrieved chunks
- **THEN** the answer identifies which chunks it was built from

#### Scenario: No relevant match means no generated answer
- **WHEN** retrieval reports no relevant match for a query
- **THEN** the system returns an explicit "I don't have that
  information" response, and generation is never invoked

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
