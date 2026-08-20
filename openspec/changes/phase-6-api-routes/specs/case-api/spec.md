## Purpose

Exposes the rules engine and RAG layer over HTTP, with routing between
them driven by intent classification, so a real conversation can drive
an actual computed, cited plan — the deliverable CLAUDE.md describes as
"a verifiable plan the citizen can act on," not a chatbot.

## ADDED Requirements

### Requirement: Chat messages create a case, route intent, and return the next step
`POST /chat/message` SHALL create a case when none is referenced,
classify the message's intent, record any extracted facts as case
answers, answer any embedded question via RAG, and return the case's
next pending question (or that none remain).

#### Scenario: An opening message creates a case
- **WHEN** `POST /chat/message` is called with no existing case
  referenced
- **THEN** a new case is created and the response references its id

#### Scenario: A question mid-intake is answered and the pending question is re-asked
- **WHEN** a message asks a general question while a question is still
  pending on the case
- **THEN** the response includes a grounded RAG answer and the same
  pending question, unanswered

### Requirement: The next pending question is queryable directly
`GET /case/{id}/next-question` SHALL return the next unanswered,
relevant question for the case, or an explicit null when none remain.

#### Scenario: A resolvable case returns null
- **WHEN** every relevant question for a case has been answered
- **THEN** `GET /case/{id}/next-question` returns null

### Requirement: Resolving a case produces the full plan or the scope-gate response
`POST /case/{id}/resolve` SHALL produce the full plan (requirements with
citations, computed fee, offices with any conflict note) once intake is
complete, or the scope-gate response for an under-16 case, per the
rules engine's existing behavior. SHALL NOT be resolved while a required
question remains unanswered; the response SHALL indicate what is still
needed instead of a partial or incorrect plan.

#### Scenario: A complete renewal case resolves to a full plan
- **WHEN** `POST /case/{id}/resolve` is called for a case with every
  required question answered
- **THEN** the response includes the resolved requirements, fee, and
  offices, each carrying its citation

#### Scenario: An incomplete case is not resolved
- **WHEN** `POST /case/{id}/resolve` is called before intake is complete
- **THEN** no plan is returned, and the response indicates the case is
  not yet ready to resolve

#### Scenario: An under-16 case returns the scope-gate response
- **WHEN** `POST /case/{id}/resolve` is called for a case whose age
  answer is under 16
- **THEN** the response is the scope-gate response, not a plan

### Requirement: Services and requirement detail are queryable
`GET /services` SHALL list the available services. `GET /requirements/
{id}` SHALL return one requirement's detail, including its citation.

#### Scenario: A requirement's detail includes its citation
- **WHEN** `GET /requirements/{id}` is called for an existing requirement
- **THEN** the response includes that requirement's source document URL
  and verified-as-of date

### Requirement: Every requirement, fee, or office in a response carries its citation
Any API response that includes a requirement, a fee, or an office SHALL
include that item's source document and verified-as-of date.

#### Scenario: A resolved plan's fee carries its citation
- **WHEN** a resolved plan is returned
- **THEN** its fee includes a source document URL and verified-as-of
  date

### Requirement: RAG responses never carry plan-shaped data
No API response produced by the RAG path (an answered question) SHALL
include a requirement, a fee, or an office. Plan-shaped data comes only
from `POST /case/{id}/resolve`.

#### Scenario: A RAG answer has no plan fields
- **WHEN** a message's embedded question is answered via RAG
- **THEN** that part of the response contains no requirement, fee, or
  office field

### Requirement: The API's interactive documentation renders
The API's OpenAPI documentation SHALL render at `/docs`.

#### Scenario: The docs endpoint renders successfully
- **WHEN** `/docs` is requested
- **THEN** it renders the interactive API documentation without error
