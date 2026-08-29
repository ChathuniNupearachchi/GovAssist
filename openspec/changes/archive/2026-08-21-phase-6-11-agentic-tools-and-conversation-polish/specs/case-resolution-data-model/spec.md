## MODIFIED Requirements

### Requirement: Chat messages are persisted per case
Every chat message, in either direction, SHALL be persisted with a
reference to exactly one case, a role (`user` or `assistant`), its
content, when it was created, an optional intent classification, an
optional list of cited chunk ids, and an optional tool-call trace
(tool name, arguments, order, and result for every tool call made while
producing that message) — forming the durable record of what a citizen
was actually told, and the audit trail of what computed the values in
it.

#### Scenario: A chat message is persisted
- **WHEN** a chat message is created
- **THEN** it references exactly one case, and has a non-null `role`,
  `content`, and `created_at`

#### Scenario: An assistant message records what it cited
- **WHEN** an assistant message answers from retrieved chunks
- **THEN** its `cited_chunk_ids` records which chunks were cited

#### Scenario: A user message may carry no citations
- **WHEN** a user message is persisted
- **THEN** its `cited_chunk_ids` may be null, since a citizen's message
  cites nothing

#### Scenario: A tool-using answer records its full tool-call trace
- **WHEN** an assistant message is produced by calling one or more tools
- **THEN** its tool-call trace records every call made — tool name,
  arguments, order, and result — for that message

#### Scenario: A message answered without tools carries no trace
- **WHEN** an assistant message is produced without calling any tool (or
  a user message is persisted)
- **THEN** its tool-call trace is null
