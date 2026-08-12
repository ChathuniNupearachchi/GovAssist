# GovAssist

A mobile app that resolves a Sri Lankan citizen's specific government
service situation into a personalised, source-traced document checklist.
Not a chatbot — the output is a verifiable plan the citizen can act on.

## What it does

Takes a citizen's situation (via chat or guided questions), evaluates it
against verified government rules, and produces:

- A personalised document checklist with every item sourced and dated
- The exact fee computed for their case
- The specific office that accepts their application
- Prerequisites flagged in the order they must happen

## Why it is different from ChatGPT

ChatGPT generates plausible answers. GovAssist evaluates conditional
rules against a citizen's specific situation and cites the exact source
document for every requirement. A wrong answer about a fee or document
sends someone on a wasted trip. We don't guess.

## Departments

Phase 1 (current): Department of Immigration & Emigration — passports
Phase 2 (later): Registration of Persons, Registrar General, Motor Traffic

## Stack

### Mobile (this repo: /govassist)

- React Native + Expo SDK 54, TypeScript strict
- NativeWind v4 (Tailwind v3 — NOT v4)
- React Navigation native stack
- Zustand for state
- Expo SecureStore for local plan storage

### Backend (/api)

- FastAPI (Python 3.12)
- PostgreSQL 16 + pgvector
- Redis (cache + Celery broker)
- Celery (scraping and re-indexing queue)
- Alembic (migrations)
- httpx + BeautifulSoup (scraper)
- pdfplumber (PDF extraction)
- Claude API (rule parsing only — never citizen-facing)
- sentence-transformers (local embeddings)
- OpenTelemetry (tracing)

### Infrastructure

- Docker Compose (local dev)
- Railway (deployment)
- Nginx (rate limiting)
- GitHub Actions (CI)

## React Native Rules

- React Native only. No web APIs, no DOM, no div/span.
  Use View, Text, Pressable.
- NEVER pass a function to style prop. NativeWind does not apply it.
  Use plain style objects. Track pressed state with onPressIn/onPressOut
  - useState.
- Do not combine className with a style function on the same element.
  Prefer style prop with tokens.
- All colours, spacing, radii and font sizes from src/theme/tokens.ts.
  Never hardcode values.
- Minimum touch target 48px (touchTarget.min).
  Minimum body font size 16px (fontSize.body).
- Every interactive element needs accessibilityRole and accessibilityLabel.
  Checkboxes and toggles also need accessibilityState.
- Component variants are string unions with a lookup object, not booleans.
  Good: variant?: "primary" | "secondary"
  Bad: isPrimary?: boolean
- TypeScript strict. No any.
- Every data surface handles four states: loading, empty, error, loaded.
- Export new components from src/components/index.ts.
- Use Ionicons from @expo/vector-icons. Never use emoji as icons.

## Backend Rules

- Every requirement shown to a citizen must have a source_document_id
  and a verified_at date. No requirement is ever generated without a
  verified source.
- Scraped content never goes live automatically. It creates a draft
  version that must be approved by a human reviewer before publishing.
- The Claude API is used for two jobs only: parsing scraped text into
  structured rules, and matching free-text situations to services.
  Citizens never receive raw LLM output.
- Embeddings run locally with sentence-transformers. No GPU needed.
- All endpoints that call the LLM are rate-limited.

## Project Structure

govassist/ React Native mobile app
src/
components/ Reusable primitives
screens/ Full screens
navigation/ React Navigation stack
theme/ tokens.ts — single source of truth
api/ Backend client
store/ Zustand stores

api/ FastAPI backend
app/
scraper/ Immigration site scraper
ingestion/ PDF extraction and rule parsing
engine/ Condition evaluator and resolver
models/ SQLAlchemy models
db/ Database connection and migrations
mcp/ MCP server tools
api/ FastAPI routes

## Screens (implemented)

1. Splash — auto-navigates to Login after 2.5s
2. Login — Google, email/password, Skip
3. Departments — four department cards, Immigration available
4. Services — Services tab (list) + Ask tab (chat)
5. Plan — PlanHeader + ChecklistItems + SourceCitations

## Key Components (implemented)

- Button (primary, secondary, ghost variants)
- Card (static and pressable)
- ChecklistItem (pending, collected, blocked)
- StatusPill (available, comingSoon, outdated)
- SourceCitation (source name + verified date)
- DepartmentCard (available + coming soon states)
- PlanHeader (fee, office, timeline)

## Users

Sri Lankan citizens, including older and less technical people,
often anxious about a government process and using the app
outdoors on a phone. Plain language, no jargon, generous
spacing, high contrast.

## Content Rules

- Every requirement shown to a user must carry its source
  and a verified-as-of date.
- Never state a fee, document or deadline without a verified source.
- The app gives guidance, not an official ruling. Say so where
  it matters.
- A wrong checklist is worse than no checklist. When in doubt,
  show nothing and explain why.

## Out of Scope (this build)

- Sinhala and Tamil — English only
- Online submission or payment
- Appointment booking
- User accounts for citizens (device storage only)
- Departments beyond Immigration (Phase 1
