## Purpose

Gives a reviewer the core workflow this whole dashboard exists for:
seeing exactly what a draft rule change would alter, and recording a
decision about it.

## ADDED Requirements

### Requirement: Pending queue combines dashboard and live drafts
The pending-review queue SHALL include every `ADMIN_DRAFT` row and every
live `RULE_VERSION` row with `status = draft`.

#### Scenario: A dashboard-seeded draft appears in the queue
- **WHEN** an `ADMIN_DRAFT` row exists for review
- **THEN** it appears in the pending queue regardless of whether any
  live `RULE_VERSION` is currently in `draft` status

### Requirement: Side-by-side comparison against the approved version
Selecting a pending item SHALL show the currently-approved version's
requirements, conditions, and fees alongside the draft's, with
differences highlighted, and a source citation and link on every
requirement in both columns.

#### Scenario: A fee change is visible in both columns
- **WHEN** a reviewer opens the seeded renewal fee-change draft
- **THEN** the approved column shows the current fee, the draft column
  shows the proposed fee, and the two are visually distinguished as
  different

### Requirement: Material changes are flagged more prominently than cosmetic ones
Differences affecting fee, document, or office SHALL be visually
distinguished as more prominent than differences that are purely
wording changes.

#### Scenario: A fee change is flagged as material
- **WHEN** the seeded draft changes the renewal fee from LKR 10,000 to
  LKR 12,000
- **THEN** the comparison view flags this difference as material,
  distinct from how it would present a wording-only change

### Requirement: Approve records a decision without changing live status
Approving a pending item SHALL record an `ADMIN_ACTION` with
`action = approve` and mark it approved in the dashboard's own view. It
SHALL NOT change `RULE_VERSION.status` on any live row.

#### Scenario: Approving the seeded draft
- **WHEN** a reviewer approves the seeded renewal fee-change draft
- **THEN** an `ADMIN_ACTION` row is created recording the approval, the
  dashboard's queue reflects the new status, and no live
  `RULE_VERSION.status` value changes

### Requirement: Reject records a reason and preserves the draft
Rejecting a pending item SHALL require a reason, SHALL record an
`ADMIN_ACTION` with `action = reject` and that reason, and SHALL leave
the draft visible in the dashboard with its rejection recorded. A
rejected draft SHALL NOT be deleted.

#### Scenario: Rejecting with a reason
- **WHEN** a reviewer rejects a pending item and supplies a reason
- **THEN** an `ADMIN_ACTION` row records the reason, and the draft
  remains visible in the dashboard showing that rejection

### Requirement: Seeded demonstration draft
The system SHALL seed one realistic `ADMIN_DRAFT` for demonstration: a
renewal fee change from LKR 10,000 to LKR 12,000, so the comparison view
has a genuine material difference to show without requiring the live
ingestion pipeline to run.

#### Scenario: Seeded draft is available immediately after setup
- **WHEN** the dashboard is set up and seeded
- **THEN** the pending queue already contains the renewal fee-change
  draft, ready to compare and act on
