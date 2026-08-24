## Purpose

Replaces the hand-written turn-handling flow with a directed graph whose
structure is inspectable and whose routing is deterministic, so a chat
turn's path through classification, fact recording, question selection,
and — for an open question — a native tool-calling cycle can be
visualized, traced, and reasoned about node by node, without letting the
model influence which node runs next.

## ADDED Requirements

### Requirement: Graph routing is deterministic, never model-selected
Which node the graph transitions to next SHALL be decided by a
deterministic Python function evaluating the current state — never by
parsing or trusting a value the model itself produced as a routing
instruction. Which intake question is asked next SHALL remain the
existing deterministic next-question selection's decision, unchanged by
this migration.

#### Scenario: A model's output cannot redirect graph routing
- **WHEN** a node's model call returns output that resembles a routing
  instruction (for example, text suggesting which node to run next)
- **THEN** the graph's next transition is still decided by the
  deterministic edge function evaluating state, not by that output

#### Scenario: Question selection is unchanged by the graph migration
- **WHEN** the graph's `next_question` node runs
- **THEN** it returns the same next question the pre-graph
  `next_question` selection would have returned for the same case state

### Requirement: The graph reproduces the pre-graph flow's behavior end to end
A full case handled through the graph SHALL produce the same
requirements, fee, offices, and citations as the pre-graph router would
have produced for the same sequence of citizen inputs, for every golden
scenario.

#### Scenario: A golden scenario matches pre-graph output
- **WHEN** a golden scenario's message sequence is replayed through the
  graph
- **THEN** the resolved plan's requirements, fee, and offices match the
  pre-graph implementation's output for that same scenario

### Requirement: The graph's structure can be exported for inspection
The graph's node and edge structure SHALL be exportable to a visual
representation, independent of running a live conversation, so the flow
can be reviewed without reading the routing code.

#### Scenario: A visualization reflects the graph's actual nodes and edges
- **WHEN** the graph's visualization is exported
- **THEN** it includes every node (`classify`, `record_facts`,
  `next_question`, `resolve`, `agent`, `tools`, `verify`) and the edges
  connecting them, including the `agent` ↔ `tools` cycle and `verify`'s
  retry edge back to `agent`

### Requirement: The open-question path is a native tool-calling cycle, not a fixed pipeline
Answering an open question SHALL be modeled as a cycle among three
nodes — `agent` (one model turn deciding to call a tool or submit an
answer), `tools` (executes whichever tool the model selected), and
`verify` (checks a submitted answer against every value a tool call
actually returned this turn) — rather than a fixed linear sequence of
retrieval, reranking, and generation steps. `agent` SHALL transition to
`tools` when the model's turn requested one or more tool calls, and
`tools` SHALL transition back to `agent` with the results. `agent` SHALL
transition to `verify` only when the model submitted a final answer.
`verify` SHALL transition back to `agent` with an explanation on a
failed check, and to the end of the turn on success or after one retry
still fails.

#### Scenario: A tool call routes through the cycle
- **WHEN** the `agent` node's model turn requests a tool call
- **THEN** the graph transitions to `tools`, executes the requested
  tool, and returns to `agent` with the result

#### Scenario: A failed verification retries once before falling back
- **WHEN** the `verify` node rejects a submitted answer
- **THEN** the graph transitions back to `agent` with an explanation of
  what failed, and a second consecutive verification failure ends the
  turn with the explicit no-relevant-match response instead of a third
  attempt

#### Scenario: Reranking is not a separate top-level graph node
- **WHEN** the `tools` node executes a `retrieve_documents` call
- **THEN** hybrid search and reranking both run inside that tool's own
  implementation — neither appears as its own node in the graph's
  exported structure

### Requirement: Conversation position is checkpointed independently of case facts
The graph's execution position within a conversation SHALL be persisted
by a checkpointer separate from `CASE_ANSWER`. `CASE_ANSWER` SHALL
remain the sole store of facts the rules engine evaluates and joins to
`CONDITION`, `REQUIREMENT`, and `RULE_VERSION` — the checkpointer SHALL
NOT duplicate or replace those facts, and SHALL NOT be read by the rules
engine.

#### Scenario: Checkpointed position does not duplicate recorded facts
- **WHEN** a case's conversation position is checkpointed
- **THEN** the checkpoint contains no fact the rules engine evaluates —
  those remain readable only from `CASE_ANSWER`

#### Scenario: Clearing the checkpoint does not lose recorded facts
- **WHEN** a case's checkpointed conversation position is cleared or
  reset
- **THEN** every fact previously recorded to `CASE_ANSWER` for that case
  is still present and still evaluated by the rules engine
