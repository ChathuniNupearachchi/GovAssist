## Purpose

Answers open-ended citizen questions ("What's the process for a lost
passport?") with a grounded, cited answer drawn from retrieved chunks —
the RAG half of CLAUDE.md's "Two kinds of question, two mechanisms" split.
This capability never produces a checklist, fee, or office routing; that
remains the rules engine's job alone.

## ADDED Requirements

### Requirement: Retrieval only searches approved content
The system SHALL only retrieve chunks belonging to `approved` source
documents. Chunks belonging to `pending` or `rejected` documents SHALL
never be returned, regardless of similarity score.

#### Scenario: A draft document's chunks are excluded
- **WHEN** a retrieval query is run
- **AND** a chunk from a `pending` or `rejected` source document is among
  the closest matches
- **THEN** that chunk is excluded from the results

### Requirement: Retrieved answers are grounded and cited
An answer returned by retrieval SHALL be generated only from the chunks
retrieved for that query, and SHALL include, for each chunk it draws on,
the chunk's source document and verified-as-of date.

#### Scenario: A relevant question returns a cited answer
- **WHEN** a citizen asks an open-ended question that matches approved
  content
- **THEN** the system returns an answer along with the source document and
  verified-as-of date of each chunk the answer draws on

### Requirement: No relevant content means no answer
When retrieval finds nothing sufficiently relevant to the question, the
system SHALL say so explicitly rather than generating an answer not
grounded in retrieved chunks.

#### Scenario: No matching chunks exist
- **WHEN** a retrieval query returns no chunks above the relevance
  threshold
- **THEN** the system responds that it could not find relevant information,
  and does not generate an answer

### Requirement: Retrieval never produces plan output
Retrieval and grounded-answer generation SHALL NOT produce a document
checklist, a fee, an office routing, or prerequisite ordering. Those
remain the sole output of the rules engine.

#### Scenario: An open-ended question does not trigger the rules engine
- **WHEN** a citizen asks an open-ended question handled by retrieval
- **THEN** the response contains no checklist, fee, or office routing

#### Scenario: A situation question still goes through the rules engine
- **WHEN** a citizen's message describes their specific situation (e.g.
  age, life event, location) rather than an open-ended question
- **THEN** the system routes it to the rules engine for plan generation,
  not to retrieval