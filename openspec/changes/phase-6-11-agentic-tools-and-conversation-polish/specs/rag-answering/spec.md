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
