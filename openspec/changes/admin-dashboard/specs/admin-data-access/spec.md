## Purpose

Guarantees, at the database level rather than by application-code
convention, that the admin dashboard can never alter any table the
citizen-facing system reads — so a bug or a future feature in the
dashboard cannot corrupt live citizen data.

## ADDED Requirements

### Requirement: Dedicated read-only Postgres role
The system SHALL provision a dedicated Postgres role granted `SELECT`
only on every table the citizen-facing system reads (`SERVICE`,
`RULE_VERSION`, `REQUIREMENT`, `CONDITION`, `REQUIREMENT_CONDITION`,
`FEE_RULE`, `QUESTION`, `OFFICE`, `SOURCE_DOCUMENT`, `DOCUMENT_CHUNK`,
`CASE`, `CASE_ANSWER`, `PLAN_ITEM`, `AUTHORIZED_STUDIO`,
`CHAT_MESSAGE`), and the admin API SHALL connect to the database using
only that role for all queries against those tables.

#### Scenario: Attempted write against a live table fails
- **WHEN** any query attempts `INSERT`, `UPDATE`, or `DELETE` against
  one of the listed live tables using the admin role's connection
- **THEN** Postgres rejects the statement with a permission error,
  independent of whether the admin API's own code attempted to prevent
  it

#### Scenario: Reads succeed normally
- **WHEN** the admin API issues a `SELECT` against any of the listed
  live tables using the admin role's connection
- **THEN** the query succeeds and returns the current live data

### Requirement: Admin-owned tables are separately writable
The dedicated role SHALL additionally be granted `INSERT`, `UPDATE`,
and `DELETE` — but only on the tables the dashboard itself owns:
`ADMIN_USER`, `ADMIN_ACTION`, `ADMIN_DRAFT`, and `ADMIN_OVERLAY`.

#### Scenario: Writes to admin-owned tables succeed
- **WHEN** the admin API writes an `ADMIN_ACTION`, `ADMIN_DRAFT`,
  `ADMIN_OVERLAY`, or `ADMIN_USER` row using the admin role's connection
- **THEN** the write succeeds

### Requirement: Admin API is a separate application
The admin backend SHALL run as a separate FastAPI application from the
citizen-facing API, with its own process, its own database connection
configuration, and no shared route or import that could let a
citizen-facing request reach admin-only logic or vice versa.

#### Scenario: Citizen-facing app is unaffected
- **WHEN** the admin dashboard is deployed, misconfigured, or taken
  down entirely
- **THEN** the citizen-facing API and mobile app continue to operate
  exactly as before, since neither depends on the admin application at
  runtime or at import time

### Requirement: Approving or rejecting in the dashboard never mutates live rule state
Recording an approve or reject decision in the dashboard SHALL write
only to `ADMIN_ACTION` (and, for a draft that only exists in the
dashboard, `ADMIN_DRAFT`'s own status). It SHALL NOT modify
`RULE_VERSION.status` or any other live table, since the role granted
to the admin API cannot do so regardless of what the application code
attempts.

#### Scenario: Citizen-facing resolution is identical before and after an approval
- **WHEN** a citizen-facing query for a resolved case is captured, an
  admin then approves a draft in the dashboard, and the same
  citizen-facing query is captured again
- **THEN** the two captured results are identical, demonstrating that
  the approval had no effect on what a citizen sees
