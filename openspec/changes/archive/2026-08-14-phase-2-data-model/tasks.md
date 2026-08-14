## 1. Dependency

- [x] 1.1 Add `pgvector` (Python package) to `api/requirements.txt`,
      pinned, and install into `api/venv`

## 2. Models (`api/app/models.py`)

- [x] 2.1 Create `api/app/models.py` with the declarative `Base`
- [x] 2.2 Add a shared UUID-primary-key convention (Python-side `uuid4`
      default) used by all 14 models, matching the pattern from the
      Phase 1 design
- [x] 2.3 Add `Service` (id, code, name, category)
- [x] 2.4 Add `SourceDocument` (id, source_url, snapshot_path,
      content_hash, document_type [html|pdf], fetched_at, status
      [pending|approved|rejected]) — this is the first change to actually
      create this model; use this exact column shape, not the shape from
      the deleted `setup-fastapi-backend` change
- [x] 2.5 Add `RuleVersion` (id, service_id FK, source_document_id FK,
      approved_by, version_number, status [draft|approved|superseded],
      verified_at)
- [x] 2.6 Add `Requirement` (id, rule_version_id FK, office_id FK
      nullable, label, kind [document|step|prerequisite], freshness_rule,
      sequence)
- [x] 2.7 Add `Condition` (id, question_id FK, attribute, operator
      [equals|lessThan|in], value) — no self-referential FK; confirm the
      model has no way to point to another `Condition`
- [x] 2.8 Add `RequirementCondition` (requirement_id FK, condition_id FK,
      negated) as a flat join table — no boolean-tree structure
- [x] 2.9 Add `FeeRule` (id, rule_version_id FK, condition_id FK nullable,
      base_amount, penalty_amount nullable, basis [normal|urgent])
- [x] 2.10 Add `Question` (id, service_id FK, prompt, answer_type
      [single|boolean|district], sequence)
- [x] 2.11 Add `Office` (id, name, type [head|regional|ds|mission],
      district as `ARRAY(String)` nullable for head office only,
      opening_hours)
- [x] 2.12 Add `Case` (id, service_id FK, device_ref, resolved_at
      nullable, outdated)
- [x] 2.13 Add `CaseAnswer` (id, case_id FK, question_id FK, value)
- [x] 2.14 Add `PlanItem` (id, case_id FK, requirement_id FK,
      rule_version_id FK, collected, sequence)
- [x] 2.15 Add `DocumentChunk` (id, source_document_id FK, chunk_text,
      embedding as `pgvector.sqlalchemy.Vector(384)`, sequence)
- [x] 2.16 Add `AdminUser` (id, email, role [reviewer|approver])
- [x] 2.17 Add a Postgres `CHECK` constraint on every restricted-value
      column named above (status, kind, operator, answer_type, type,
      basis, role, document_type) enumerating its allowed values

## 3. Migration

- [x] 3.1 Run `alembic revision --autogenerate -m "create phase 2 data
      model"` from `api/` and confirm `migrations/env.py`'s
      `from app.models import Base` now resolves (no longer the expected
      Phase 1 failure)
- [x] 3.2 Review the generated migration against all 14 models —
      autogenerate won't catch `CHECK` constraints or the pgvector column
      type reliably; add/fix them by hand if missing
- [x] 3.3 Add `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` at the
      start of `upgrade()`
- [x] 3.4 Add `op.execute("DROP EXTENSION IF EXISTS vector")` at the end
      of `downgrade()`
- [x] 3.5 Add seed data inserts to `upgrade()` (via `op.bulk_insert`):
      the Battaramulla head office, and five regional offices with their
      district arrays:
      - Head Office — Battaramulla, type `head`, district `NULL`
      - Kandy — type `regional`, districts: Kandy, Matale, Nuwara Eliya,
        Badulla, Monaragala
      - Matara — type `regional`, districts: Matara, Galle, Hambantota
      - Vavuniya — type `regional`, districts: Vavuniya, Mannar,
        Mullaitivu, Anuradhapura, Polonnaruwa
      - Kurunegala — type `regional`, districts: Kurunegala, Puttalam,
        Colombo, Gampaha, Kalutara, Kegalle, Ratnapura, Ampara,
        Batticaloa, Trincomalee
      - Jaffna — type `regional`, districts: Jaffna, Kilinochchi
      (all 25 districts covered exactly once across the five regional
      offices — verify against Sri Lanka's district list before applying)
- [x] 3.6 Add matching `DELETE` statements for exactly the seeded rows in
      `downgrade()` (not a blanket table wipe)

## 4. Verification (Done-when criteria)

- [x] 4.1 `alembic upgrade head` creates all 14 tables cleanly
      against the local Docker Postgres
- [x] 4.2 `alembic downgrade -1` rolls back cleanly — no tables, no seed
      rows, `vector` extension removed
- [x] 4.3 Re-run `alembic upgrade head` after the downgrade to confirm the
      migration is idempotent in both directions
- [x] 4.4 Query every one of the 25 districts against the seeded `office`
      table and confirm each resolves to exactly one office
- [x] 4.5 Confirm the `vector` extension is enabled and
      `document_chunk.embedding` is `vector(384)` (e.g. via
      `\d document_chunk` in `psql` or an equivalent inspection query)
- [x] 4.6 Confirm `condition.operator`'s `CHECK` constraint rejects a
      fourth value (e.g. attempt an insert with `operator = 'greaterThan'`
      and confirm it fails)