## Purpose

Makes a citizen's turn through the system inspectable end to end — every
model call, tool call, and graph transition that produced a given
response, linked back to the case it belongs to — for debugging and
demo purposes, self-hosted so no conversation content leaves GovAssist's
own infrastructure.

## ADDED Requirements

### Requirement: Every LLM call, tool call, and graph transition is traced
Every call to an LLM, every tool call, and every graph node transition
made while handling a turn SHALL be recorded as a trace, capturing at
minimum what was called, its inputs, its result, and its position in
the turn's sequence.

#### Scenario: A multi-step turn's trace covers every call and transition
- **WHEN** a turn involves more than one LLM call, tool call, or graph
  node transition
- **THEN** the resulting trace records every one of them, in the order
  they occurred

### Requirement: Every trace is linked to its case
Every trace produced while handling a turn SHALL be linked to the
`case_id` of the case that turn belongs to, so traces for a given
citizen's conversation can be retrieved together.

#### Scenario: Traces for one case are retrievable together
- **WHEN** a case has had more than one traced turn
- **THEN** every trace for that case can be retrieved by its `case_id`

### Requirement: Tracing runs self-hosted
Tracing SHALL run against a self-hosted tracing service, with no
conversation content sent to an external, third-party-hosted tracing
service.

#### Scenario: No trace data leaves self-hosted infrastructure
- **WHEN** a trace is recorded
- **THEN** it is written only to the self-hosted tracing service, not to
  any external SaaS endpoint
