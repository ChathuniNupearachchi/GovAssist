## Purpose

Lets a human reviewer authenticate to the admin dashboard as a distinct
identity from any citizen-facing account, so every review action can be
attributed to a specific person.

## ADDED Requirements

### Requirement: Admin signup
The system SHALL provide `POST /admin/auth/signup` accepting an email,
a password, and a role, and SHALL create an `ADMIN_USER` row with a
bcrypt-hashed password. The system SHALL NOT store or log a plaintext
password at any point.

#### Scenario: Successful signup
- **WHEN** a request supplies a unique email, a password, and role
  `reviewer` or `approver`
- **THEN** an `ADMIN_USER` row is created with `password_hash` set and
  the response never echoes the plaintext password

#### Scenario: Duplicate email rejected
- **WHEN** a signup request supplies an email that already exists in
  `ADMIN_USER`
- **THEN** the system rejects the request without creating a second row

### Requirement: Admin signin
The system SHALL provide `POST /admin/auth/signin` accepting an email
and password, verifying the password against the stored bcrypt hash,
and returning a signed JWT bearer token on success.

#### Scenario: Successful signin
- **WHEN** a request supplies an email and the matching plaintext
  password for an existing `ADMIN_USER`
- **THEN** the system returns a JWT that identifies that admin user

#### Scenario: Wrong password rejected
- **WHEN** a request supplies an email that exists but a password that
  does not match the stored hash
- **THEN** the system rejects the request and issues no token

### Requirement: Admin routes require authentication
Every admin dashboard route other than signup and signin SHALL require
a valid, unexpired JWT issued by `/admin/auth/signin`, verified
independently of the citizen-facing system's own JWT secret and token
issuance.

#### Scenario: Request without a token
- **WHEN** a request to any protected admin route carries no bearer
  token
- **THEN** the system rejects it with an authentication error and
  performs no database read or write

#### Scenario: Request with a citizen-facing token
- **WHEN** a request to a protected admin route carries a valid JWT
  issued by the citizen-facing app's own auth system rather than
  `/admin/auth/signin`
- **THEN** the system rejects it, since the two token spaces are
  independent

### Requirement: Single enforced role for this build
The `ADMIN_USER.role` column SHALL accept `reviewer` and `approver`,
but the system SHALL NOT gate any behavior differently between the two
roles unless that distinction is genuinely enforced somewhere in this
build.

#### Scenario: Both roles reach the same dashboard
- **WHEN** an admin with role `reviewer` and another with role
  `approver` each sign in
- **THEN** both reach the same dashboard views and can perform the same
  approve/reject actions, since no role-gated behavior exists in this
  build
