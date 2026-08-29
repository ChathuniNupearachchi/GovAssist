## Purpose

Demonstrates, in one view, why rule versioning and approval matter to a
citizen who already has a saved plan — by showing which saved plans were
built on a rule version that has since been superseded.

## ADDED Requirements

### Requirement: Saved plans are shown against their rule version
The dashboard SHALL show live saved `CASE` rows (cases with a resolved
plan) alongside the `RULE_VERSION` each was resolved against.

#### Scenario: Real cases appear
- **WHEN** the outdated-plan view is loaded
- **THEN** it lists real, live saved cases and the rule version each
  was actually resolved with

### Requirement: A plan on a superseded version is flagged
The dashboard SHALL compute, without writing to any live table, whether
a case's resolved rule version has since been superseded by a newer
approved version for the same service, and SHALL flag any such case as
outdated.

#### Scenario: A superseded case is flagged
- **WHEN** a case was resolved against a rule version that is no longer
  the current approved version for its service
- **THEN** the dashboard flags that case as outdated

#### Scenario: Flagging is read-only
- **WHEN** the dashboard computes the outdated flag for any case
- **THEN** no live `CASE`, `CASE.outdated`, or `RULE_VERSION` row is
  written to as a result — the flag exists only in the dashboard's
  computed view
