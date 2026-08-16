## Context

See proposal.md for motivation. Two schema questions were resolved with
the user before writing specs (not left open here):

1. `REQUIREMENT` and `FEE_RULE` get their own nullable `source_document_id`,
   independent of `RULE_VERSION.source_document_id` — the renewal rule
   version's facts span two documents (id=8 for documents/fees/offices,
   id=7 for fingerprints and the office conflict), and every citizen-facing
   fact needs its own citation, not an inherited one.
2. The office-resolver's conflict note lives in a new `RESOLUTION_NOTE`
   table, not a Python constant — it is citizen-facing (it changes what
   the citizen does before traveling) and CLAUDE.md's "rules live in
   data, not code" applies to it as much as to any document or fee.
   Table count is explicitly not a constraint per the user.

All facts entered as rule data were verified directly against the local
extracted text of `pages_e.php?id=7`, `id=8`, and `id=10` (Phase 3's
ingested snapshots) before this document was written — every fee,
document, prerequisite, and the office conflict matched the live source
word for word, including the exact "section 19(2)" citation.

## Goals / Non-Goals

**Goals:**
- One approved, cited `RULE_VERSION` for adult passport renewal; a
  second, independent one for passport amendment.
- Pure, unit-testable engine functions with no API surface.
- Every engine function is deterministic given the same case answers.

**Non-Goals:**
- No under-16 rule content beyond the scope-gate response (see
  BACKEND_PLAN.md Phase 4's scope gate — a real under-16 build is future
  work).
- No API routes, no chat intake, no caching (Phase 6/8).
- No resolution of the amendment alternative's own conditional logic
  beyond its two documents and fee — it is surfaced as a fixed offer, not
  independently intake-driven, in this phase.

## Decisions

### Amendment is a second, independent service, not a branch of renewal
`passport-amendment` gets its own `SERVICE`, `RULE_VERSION`, `FEE_RULE`,
and two `REQUIREMENT` rows (passport, marriage certificate), all citing
`pages_e.php?id=10`. Alternative considered: encode amendment as
conditional data hanging off the renewal rule version. Rejected — the
citation-per-fact principle means amendment's document should not
inherit "renewal, id=8" as anything, and a second lightweight service
keeps the renewal resolver's "surface the alternative" logic to a plain
lookup of another service's fee/requirements, not a special case grafted
onto renewal's own condition set.

### `Condition.attribute` names the semantic fact, not the raw question text
Each condition's `attribute` is a fixed snake_case tag (`age`,
`name_changed`, `holds_passport`, `dual_citizen`, `section_19_2`,
`profession`, `buddhist_priest`, `district`, `service_basis`) that the
engine and the golden tests refer to by name. The evaluator still looks
up the case's answer via `condition.question_id` (the FK is the source of
truth); `attribute` exists for readability and for the requirement
resolver's dual-citizen-set-selection logic, which checks `attribute =
'dual_citizen'` conditions specifically to decide which set to return.

### `in`-operator values are comma-separated
`CONDITION.value` is a single string column. For `operator = 'in'`
(used for district-based office eligibility and similar membership
checks), the value is stored as a comma-separated list (e.g.
`"Kandy,Matara,Vavuniya,Kurunegala,Jaffna"`) and the evaluator splits on
`,` before membership testing. No new column added — reversible and
consistent with the existing `String` type.

### Requirement resolver selects standard vs. dual-citizen by a single condition attribute, not by set difference
The resolver does not compute "dual-citizen set minus standard set" or
attempt to merge and de-duplicate. Every renewal requirement is tagged
with exactly one `REQUIREMENT_CONDITION` link on an `attribute =
'dual_citizen'` condition: standard-set requirements link to it
`negated = true` (apply when NOT dual citizen), dual-citizen-set
requirements link to it un-negated. This guarantees the two sets are
mutually exclusive by construction, not by resolver logic that could
drift.

### Office resolver precedence (stated, deterministic)
1. Start from the full accepting-office list for the service (Head
   Office, the five Regional Offices, Overseas Missions) — never
   Divisional Secretariats, which are excluded at the seed-data level
   (no `REQUIREMENT` or office-eligibility row ever references a `type =
   ds` office for renewal).
2. District answer narrows Regional Offices to the one(s) whose
   `OFFICE.district` array contains the citizen's district; Head Office
   and Missions remain listed regardless of district (the source draws
   no district restriction on Head Office).
3. If `service_basis = urgent`, attach the seeded `RESOLUTION_NOTE`
   (looked up by a fixed `code = 'urgent_office_conflict'`) to the
   result. The note's presence does not remove any office from the
   list — the conflict is "confirm before traveling," not "this office
   is excluded."
4. Office order in the returned list is always: Head Office, then
   Regional Office(s) (alphabetical), then Missions — fixed, not
   dependent on iteration order of any set/dict, so repeated calls are
   byte-identical.

### `RESOLUTION_NOTE` shape
`id, code (unique string, e.g. "urgent_office_conflict"), note_text,
primary_source_document_id (FK, not null), secondary_source_document_id
(FK, nullable), created_at`. The `code` gives the office resolver a
stable, data-driven lookup key without parsing note text or trigger
conditions — a future conflict gets a new row with a new `code`, and the
resolver function that needs it is a one-line addition, not a schema
change.

### Golden test scenarios are data fixtures, not hardcoded assertions in engine code
Each of the ten scenarios (`api/tests/engine/golden_scenarios.py`) is a
dict of case answers plus the hand-verified expected requirement labels,
fee amount, office list, and any scope-gate/amendment-alternative flag.
The test loops over them and calls the real resolver — no scenario
special-cases the resolver itself.

## Risks / Trade-offs

- [Risk] The under-16 scope gate is easy to bypass accidentally if a
  future change reorders intake questions. → Mitigation: age is
  evaluated first and unconditionally in the resolver's entry point,
  before any other question is read, and a golden scenario asserts this.
- [Risk] `Condition.attribute` is an unenforced convention (a free-text
  string), so a typo (e.g. `dual_citzen`) would silently break the
  standard/dual-citizen split. → Mitigation: seed script asserts the
  full set of expected attribute values exists before marking the rule
  version approved; golden scenario 6 (dual citizen) and 7 (Buddhist
  priest, standard set) both fail loudly if the split is wrong.
- [Risk] Two `SourceDocument` rows exist per URL (id=7, id=8, id=10) from
  Phase 3's re-scrape (content differs only by a live visitor counter,
  per Phase 3's design.md). Rule data must cite a consistent one. →
  Mitigation: seed script resolves each URL's `SourceDocument` by
  `source_url` ordered by `fetched_at` ascending (the first/original
  fetch), so citations are stable and not dependent on re-scrape timing.

## Migration Plan

One Alembic migration: add `source_document_id` (nullable FK) to
`requirement` and `fee_rule`; create `resolution_note`. Reversible —
downgrade drops the new table and the two new columns, leaving the
other 13 Phase 2 tables untouched.
