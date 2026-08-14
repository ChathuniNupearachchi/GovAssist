# office-directory Specification

## Purpose

Defines the persisted directory of accepting offices and guarantees that
every citizen, regardless of which of Sri Lanka's 25 districts they're
applying from, resolves to exactly one accepting office — the data
office-routing logic in later phases will depend on.

## Requirements

### Requirement: Offices are persisted with a type and district
Every office SHALL carry a name, a type (`head`, `regional`, `ds`, or
`mission`), a district (nullable only for the head office, which is not
district-scoped), and its opening hours.

#### Scenario: An office is persisted
- **WHEN** an office is created
- **THEN** it has a non-null `name`, `type`, and `opening_hours`

#### Scenario: Office type is restricted
- **WHEN** an office's type is set
- **THEN** the value is one of `head`, `regional`, `ds`, or `mission`

### Requirement: The office directory is seeded with Head Office and five regional offices
The system SHALL seed one head office in Battaramulla and five regional
offices: Kandy, Matara, Vavuniya, Kurunegala, and Jaffna.

#### Scenario: Seed offices exist after migration
- **WHEN** the Phase 2 migration has been applied
- **THEN** the office table contains the Battaramulla head office and the
  five named regional offices

### Requirement: Every district resolves to exactly one accepting office
The system SHALL seed a mapping from every one of Sri Lanka's 25 districts
to exactly one accepting office, so no citizen's district is left
unroutable.

#### Scenario: Every district maps to an office
- **WHEN** each of the 25 Sri Lankan districts is looked up in the
  district-to-office mapping
- **THEN** each one resolves to exactly one office

#### Scenario: No district is left unmapped
- **WHEN** the full set of districts in the mapping is compared against
  Sri Lanka's 25 districts
- **THEN** the two sets are identical