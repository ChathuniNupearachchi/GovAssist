## Purpose

Lets an open question that spans more than one system capability — a
fee lookup, a document lookup, a comparison between two service paths —
be answered by chaining read-only tool calls into the rules engine and
RAG retrieval, while keeping every fee, office, timeline, and
requirement value traceable to a tool result rather than model output.

## ADDED Requirements

### Requirement: Every plan-shaped value in a response comes from a tool result
A generated response SHALL NOT state a fee amount, an office name, a
processing timeline, or a document/step/prerequisite requirement unless
that value was returned by a tool call made during that same turn. The
model selects which tools to call and composes the surrounding prose;
it does not compute, estimate, or recall such a value on its own.

#### Scenario: A fee mentioned in an answer traces to a tool result
- **WHEN** a generated response states a fee amount
- **THEN** a `get_fee` (or `resolve_case` / `compare_amendment_vs_renewal`)
  tool call made during that turn returned that exact amount

#### Scenario: An office mentioned in an answer traces to a tool result
- **WHEN** a generated response names an office
- **THEN** a `find_office` (or `resolve_case`) tool call made during that
  turn returned that office

#### Scenario: A response never invents a value no tool returned
- **WHEN** a generated response is produced
- **THEN** every fee, office, timeline, and requirement value in it can
  be attributed to a specific tool call result from that turn

### Requirement: A comparison question chains multiple tool calls
A question that requires comparing two service paths (for example,
amending versus renewing) SHALL be answered by calling the tools needed
to compute each path's values separately and composing the comparison
from those results — not by a single tool call, and not by the model
inferring one path's numbers from the other's.

#### Scenario: An amend-vs-renew question calls fee lookup for both paths
- **WHEN** a citizen asks whether they should amend their passport or
  get a new one
- **THEN** the response is produced only after the fee for both the
  amendment path and the renewal path has been retrieved via separate
  tool calls (or via `compare_amendment_vs_renewal`, which itself makes
  both lookups), and at least one document lookup has been made

#### Scenario: A comparison exists in no single document
- **WHEN** a comparison response is returned
- **THEN** its content combines results from more than one tool call,
  not the content of a single retrieved passage

### Requirement: Every tool call is logged as a per-turn trace
Every tool call made while answering a turn SHALL be recorded — the tool
name, its arguments, the order it was called in, and its result — as a
retrievable trace for that turn.

#### Scenario: A multi-step turn's trace is retrievable
- **WHEN** a turn involves more than one tool call
- **THEN** the recorded trace for that turn lists every call in the
  order it happened, each with its tool name, arguments, and result

#### Scenario: A trace exists even for a single-tool turn
- **WHEN** a turn is answered using exactly one tool call
- **THEN** a trace recording that one call is still produced

### Requirement: A malformed tool call does not crash the turn
If the model requests a tool call with arguments that do not match that
tool's expected shape, the system SHALL handle this without an unhandled
exception reaching the citizen — either by returning a tool error result
the model can react to, or by falling back to the explicit
no-relevant-match response.

#### Scenario: Malformed tool arguments are handled, not crashed on
- **WHEN** a tool call's arguments do not satisfy the tool's expected
  parameters
- **THEN** the turn completes with either a corrected follow-up tool
  call or the explicit no-relevant-match response, never an unhandled
  server error
