## Purpose

Defines the hand-entered, cited rule content that must exist in the
database for adult passport renewal and passport amendment before the
resolution engine has anything to resolve against — what data must be
true, not how it gets evaluated.

## ADDED Requirements

### Requirement: Adult passport renewal has one approved rule version
The system SHALL have exactly one `RULE_VERSION` with `status =
approved` for a `passport-renewal` service, with `RULE_VERSION.
source_document_id` citing `pages_e.php?id=8` and a non-null
`verified_at`.

#### Scenario: The renewal rule version is approved
- **WHEN** the `passport-renewal` service's rule versions are queried
- **THEN** exactly one has `status = approved`, and it cites
  `pages_e.php?id=8`

### Requirement: The standard document set is complete and cited
The renewal rule version SHALL include requirements for: a photo studio
acknowledgement (kind `prerequisite`, sequenced before every `document`
requirement); an original birth certificate with photocopy; an original
National Identity Card with photocopy; a current passport with a
photocopy of the bio-data page, gated on the applicant holding one; a
marriage certificate with photocopy, gated on a name change since
issuance; an educational certificate and service-confirming document
with photocopies, gated on a stated profession; and a Samanera or Higher
Ordination certificate with photocopies, gated on the applicant being a
Buddhist priest. Every one of these requirements SHALL carry a
`source_document_id` citing `pages_e.php?id=8`.

#### Scenario: The photo studio acknowledgement is a prerequisite
- **WHEN** the standard document set's requirements are queried by
  `sequence`
- **THEN** the photo studio acknowledgement requirement has `kind =
  prerequisite` and a lower sequence than every `document` requirement

#### Scenario: Conditional documents are gated, not always included
- **WHEN** the marriage certificate, educational/service documents, and
  Samanera/Higher Ordination certificate requirements are inspected
- **THEN** each is linked via `REQUIREMENT_CONDITION` to the condition
  that gates it (name changed, profession stated, Buddhist priest)
  rather than being unconditional

### Requirement: The dual-citizen document set replaces the standard set
The renewal rule version SHALL include a separate set of requirements for
dual citizens — completed application form; photo studio acknowledgement;
dual citizenship certificate with photocopy; foreign passport (plus any
Sri Lankan passport held) with photocopies of bio-data pages; National
Identity Card with photocopy; birth certificate with photocopy — each
gated on the applicant being a dual citizen, and none of the standard
set's non-dual-citizen requirements SHALL be gated to also apply to a
dual-citizen case. Every dual-citizen requirement SHALL carry a
`source_document_id` citing `pages_e.php?id=8`.

#### Scenario: A dual-citizen case's requirements are the dual-citizen set
- **WHEN** requirements are filtered to those whose gating conditions
  pass for a dual-citizen case
- **THEN** the result is exactly the dual-citizen document set, and none
  of the standard set's requirements (birth certificate under the
  standard label, NIC under the standard label, etc.) also pass

### Requirement: A new NIC is a blocking prerequisite for section 19(2) dual citizens
The renewal rule version SHALL include a `prerequisite` requirement
requiring a new National Identity Card, gated on the applicant having
obtained dual citizenship under section 19(2) of the amended Citizenship
Act 18 of 1948, citing `pages_e.php?id=8`.

#### Scenario: A section 19(2) case includes the new-NIC prerequisite
- **WHEN** a dual-citizen case's answers indicate citizenship was
  obtained under section 19(2)
- **THEN** the resolved requirements include the new-NIC prerequisite

### Requirement: Renewal fees are cited and split by basis
The renewal rule version SHALL include two fee rules: `basis = normal`
with `base_amount = 10000.00`, and `basis = urgent` with `base_amount =
20000.00`, each citing `pages_e.php?id=8`.

#### Scenario: Both fee bases exist
- **WHEN** the renewal rule version's fee rules are queried
- **THEN** exactly one has `basis = normal` and `base_amount = 10000.00`,
  and exactly one has `basis = urgent` and `base_amount = 20000.00`

### Requirement: Fingerprints are a cited, in-person prerequisite
The renewal rule version SHALL include a `prerequisite` requirement for
fingerprint collection, gated on applicant age being at least 16 and at
most 60, citing `pages_e.php?id=7`, and its label SHALL state that
collection happens in person at the Head Office or a Regional Office
only.

#### Scenario: Fingerprints requirement is cited to the correct document
- **WHEN** the fingerprints requirement is inspected
- **THEN** its `source_document_id` cites `pages_e.php?id=7`, not
  `pages_e.php?id=8`

### Requirement: Accepting offices are seeded and Divisional Secretariats are excluded
`OFFICE` rows SHALL exist for the Head Office (Battaramulla) and the five
Regional Offices (Kandy, Matara, Vavuniya, Kurunegala, Jaffna) and at
least one `mission`-type office, and no requirement or office resolution
input for renewal submission SHALL reference an office of `type = ds`.

#### Scenario: No DS office is ever an accepting office for renewal
- **WHEN** the set of offices renewal submission can resolve to is
  queried
- **THEN** it contains only `head`, `regional`, and `mission` type
  offices, never `ds`

### Requirement: The urgent-service office conflict is recorded as a resolution note
A `RESOLUTION_NOTE` SHALL exist stating that one-day (urgent) service's
availability at Regional Offices is disputed between two passages of
`pages_e.php?id=7`, and SHALL reference `pages_e.php?id=7` as both its
citations (the "only available at Head Office" passage and the working
hours passage listing one-day service at Regional Offices).

#### Scenario: The conflict note is retrievable
- **WHEN** resolution notes relevant to urgent-service office routing are
  queried
- **THEN** exactly one is found, and it references `pages_e.php?id=7`

### Requirement: Passport amendment exists as a separate, lightweight approved rule version
The system SHALL have exactly one `RULE_VERSION` with `status = approved`
for a `passport-amendment` service, citing `pages_e.php?id=10`, with one
fee rule (`base_amount = 1200.00`) and requirements for the passport and
the marriage certificate, each carrying their own `source_document_id`
citing `pages_e.php?id=10`.

#### Scenario: The amendment rule version is independently approved
- **WHEN** the `passport-amendment` service's rule versions are queried
- **THEN** exactly one has `status = approved`, its fee rule has
  `base_amount = 1200.00`, and it cites `pages_e.php?id=10`
