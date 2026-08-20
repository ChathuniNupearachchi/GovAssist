## MODIFIED Requirements

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
nothing relevant.

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

## ADDED Requirements

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
