## Purpose

Lets an authorized reviewer or approver edit the service catalogue
(requirements, conditions, fees, offices) through the API instead of a
direct database edit — built last, only once every prior capability in
this change is passing, per this change's own sequencing.

## ADDED Requirements

### Requirement: Service catalogue edits require JWT authentication
Every route that creates, updates, or deletes a requirement, condition,
fee, or office SHALL require a valid JWT identifying an `ADMIN_USER`
with role `reviewer` or `approver`. A request without a valid JWT SHALL
be rejected without performing the edit.

#### Scenario: An unauthenticated edit is rejected
- **WHEN** a request to edit a requirement, condition, fee, or office
  carries no valid JWT
- **THEN** the request is rejected, and no edit is performed

#### Scenario: An authenticated reviewer can edit the catalogue
- **WHEN** a request carries a valid JWT for an `ADMIN_USER` with role
  `reviewer` or `approver`
- **THEN** the requested create, update, or delete is performed

### Requirement: The admin catalogue routes cover requirements, conditions, fees, and offices
The admin API SHALL expose create, update, and delete operations for
each of: requirements, conditions, fees, and offices.

#### Scenario: Every catalogue entity type is editable
- **WHEN** the admin API's routes are inspected
- **THEN** requirements, conditions, fees, and offices each have create,
  update, and delete operations available
