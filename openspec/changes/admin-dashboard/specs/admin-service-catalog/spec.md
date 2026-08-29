## Purpose

Lets a reviewer see every live service's current rule content with its
citations, and record catalog-level edits locally without ever moving
live rule data.

## ADDED Requirements

### Requirement: Service list reflects live data
The dashboard SHALL list all services present in the live `SERVICE`
table (the seven Immigration &amp; Emigration services at the time of
this build: renewal, new passport, lost or stolen, amendment, under-16,
child name deletion, emergency certificate), each with its name, code,
category, requirement count, condition count, question count, current
rule version, and last verified date, all computed from live data.

#### Scenario: All seven services appear
- **WHEN** the service catalog is loaded
- **THEN** all services currently in the live `SERVICE` table appear,
  each with counts and a verified date matching the underlying data

### Requirement: Hand-verified rules display as approved
A service's current rule version SHALL display as **approved**, not
pending, when its `RULE_VERSION.status` is `approved` in the live data
— including every rule version that was hand-entered and verified
against its source pages during development, since that verification is
exactly what a reviewer would otherwise be asked to redo.

#### Scenario: An existing hand-entered service shows approved
- **WHEN** the service catalog shows a service whose live
  `RULE_VERSION.status` is `approved`
- **THEN** the dashboard displays it as approved, never as pending or
  unreviewed

### Requirement: Drill-down shows requirements with citations
Selecting a service SHALL show its requirements, conditions, fee rules,
and questions, each with its source citation (source document and link
to the original page or PDF) so a reviewer can check the claim against
the source.

#### Scenario: Every requirement links to its source
- **WHEN** a reviewer drills into a service
- **THEN** every requirement, condition, and fee rule shown carries a
  citation identifying its source document, and that citation links to
  the original page or PDF

### Requirement: Catalog edits are overlay-only
Create, update, and delete actions on a service in this catalog SHALL
write only to `ADMIN_OVERLAY` and SHALL be reflected in the dashboard's
own view. They SHALL NOT modify any live `SERVICE`, `RULE_VERSION`,
`REQUIREMENT`, `CONDITION`, or `FEE_RULE` row.

#### Scenario: An overlay edit appears in the dashboard, not live data
- **WHEN** a reviewer edits a service's displayed detail through the
  dashboard
- **THEN** an `ADMIN_OVERLAY` row is written, the dashboard's own view
  reflects the edit, and the underlying live rule tables are unchanged
