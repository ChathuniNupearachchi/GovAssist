## Purpose

Exposes the already-seeded, already-resolvable authorized-photo-studio
directory (1,420 studios across 25 districts, `app.engine.studios.
resolve_studios`) over HTTP, so a citizen's Plan screen can show which
studios accept their district's photo requirement — data that exists
today but that no API client can reach.

## ADDED Requirements

### Requirement: Authorized studios are queryable by district
`GET /studios` SHALL accept a `district` query parameter (in this
project's canonical district spelling) and return every authorized
photo studio in that district, ordered by name, reusing the existing
`resolve_studios` engine function unchanged.

#### Scenario: A district with authorized studios
- **WHEN** `GET /studios?district=Colombo` is called
- **THEN** the response lists every authorized studio in Colombo,
  ordered by name

#### Scenario: A district with no seeded studios
- **WHEN** `GET /studios` is called with a valid district that has no
  authorized studios on record
- **THEN** the response returns an empty studio list, not an error

#### Scenario: A missing or unrecognized district
- **WHEN** `GET /studios` is called with no `district` parameter, or one
  outside the 25 canonical districts
- **THEN** the response is a 422 naming the problem, not a silent empty
  list

### Requirement: Every studio carries its citation, and the response always carries the receipt note
Each returned studio SHALL include a citation (source document and
verified-as-of date). The response SHALL always include the standing
receipt-submission note, regardless of which studio the citizen visits.

#### Scenario: A studio's citation is present
- **WHEN** any studio is returned
- **THEN** it includes a non-null source document id, source URL, and
  verified-at date

#### Scenario: The receipt note is always present
- **WHEN** `GET /studios` returns any result, including an empty studio
  list
- **THEN** the response includes the note that the studio's
  acknowledgement note must be submitted with the application
