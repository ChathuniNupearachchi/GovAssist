## MODIFIED Requirements

### Requirement: Retrieval ranks candidates by a blend of vector similarity and full-text relevance, then reranks before generation
Retrieval SHALL rank candidate chunks using both semantic similarity
(vector search) and exact-term relevance (full-text search) against the
query, combined into a single ranking, rather than vector similarity
alone. That blended ranking SHALL then produce a wider candidate pool
than is passed to generation; a dedicated reranking stage (see
`retrieval-reranking`) SHALL rescore that pool against the query and
select the subset actually passed to generation. Approval-only scoping
and the weak-match reformulation-retry behavior are unaffected by
either change; only the ranking and selection beneath them changes.

#### Scenario: An exact identifier retrieves correctly via blended ranking
- **WHEN** a query names a specific identifier that appears verbatim in
  the corpus (for example, a form number or a section reference)
- **THEN** the chunk containing that identifier ranks as a top result,
  even when vector similarity alone would not have ranked it highly

#### Scenario: A genuinely covered query outranks an uncovered one
- **WHEN** a query about content the corpus actually covers is compared
  against a query about a topic the corpus does not cover
- **THEN** the covered query's top match is accepted as relevant and the
  uncovered query's top match is not, under the reranked accept/reject
  threshold

#### Scenario: Generation sees the reranked selection, not the raw blended ranking
- **WHEN** a query is answered
- **THEN** the chunks passed to generation are the reranker's top
  selection from the blended-ranking candidate pool, not the raw
  blended ranking itself

### Requirement: A weak match triggers one reformulation retry before giving up
After retrieving and reranking chunks for a query, the system SHALL
assess whether the top result is strong enough to answer from, requiring
both the pre-rerank hybrid signal and the reranker's own calibrated
threshold to agree (see `retrieval-reranking`). When it is not, the
system SHALL reformulate the query once and retry retrieval and
reranking. When the reformulated retry is still weak, the system SHALL
return an explicit "no relevant match" result rather than proceeding to
generation.

#### Scenario: A weak initial match is retried once
- **WHEN** the top reranked result for a query is a weak match
- **THEN** the system retries retrieval and reranking once with a
  reformulated query before deciding there is no relevant match

#### Scenario: A still-weak retry yields no relevant match
- **WHEN** both the original query and its one reformulation retry
  produce only weak reranked matches
- **THEN** retrieval reports no relevant match, and generation is not
  invoked
