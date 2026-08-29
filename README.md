# GovAssist

A mobile app that turns a Sri Lankan citizen's specific situation into a
personalised, source-traced document checklist for government services.

Not a chatbot. The output is a verifiable plan you can act on.

---

## The problem

Getting anything done with a Sri Lankan government department means finding out
which office handles it, what documents you need, what it costs, and how long it
takes. That information is scattered across department websites, PDFs and gazette
notices, often out of date, and it changes depending on your specific circumstances.

Ask a general-purpose AI and you get a plausible answer. A wrong answer about a
fee or a required document sends someone on a wasted trip to Colombo.

## What GovAssist does

You describe your situation — in chat or through guided questions — and the system
evaluates it against verified government rules to produce:

- A personalised document checklist, with a source and verified-as-of date on
  every item
- The exact fee computed for your case, including conditional penalties
- The specific office that accepts your application
- Prerequisites flagged in the order they must happen

Every requirement traces back to a real government document, stored as a snapshot
with a content hash and fetch timestamp.

## Why this isn't a wrapper

The value is in the rules engine, not retrieval. Sri Lankan passport rules branch
on at least ten variables — age, passport status, dual citizenship, name changes,
guardian situation for minors, adoption, occupation, urgency, district, and whether
you're applying from abroad. Several of those open sub-trees of their own.

A general model cannot reliably compose all of that for one person's situation, and
it cannot tell you which gazette said so. GovAssist can.

---

## Scope

**Phase 1 (current)** — Department of Immigration & Emigration: passports

**Phase 2 (later)** — Department for Registration of Persons, Registrar General's
Department, Department of Motor Traffic

English only for this build.

---

## Architecture

```
Mobile app  ──HTTPS──>  Load balancer / rate limiter
                              │
                    ┌─────────┴─────────┐
                    │                   │
              FastAPI backend    Admin review console
                    │                   │
              MCP server              │
                    │                   │
              Rules engine ────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   PostgreSQL    Redis     Object storage
   + pgvector    cache     (page snapshots)
        │
   Ingestion queue ──> Scraper ──> immigration.gov.lk
                   └─> Embedding indexer
```

Scraped content never goes live automatically. It creates a draft version that a
human reviewer must approve before publishing. That approval gate is what makes
the "verified" claim honest.

---

## Tech stack

### Mobile app

| Technology | Why |
|---|---|
| React Native + Expo | Runs on a judge's own phone via QR code, no build setup |
| TypeScript | Intake answers and plan items are typed structures — catch mismatches at compile time |
| NativeWind | Tailwind class names in React Native |
| React Navigation | Screen stack for departments, services, chat, plan |
| Zustand | Small state store for the in-progress case; Redux is overkill here |
| Expo SecureStore | Saved plans on device, encrypted at rest, no account needed |

### Backend

| Technology | Why |
|---|---|
| Python 3.12 | Rules engine, parsing and embedding all live in Python |
| FastAPI | Async, and auto-generates OpenAPI docs |
| Pydantic | Validates intake payloads and rule structures — malformed conditions produce wrong plans |
| MCP Python SDK | Exposes services and case resolution as callable tools |
| SQLAlchemy + Alembic | Migrations matter — the rule schema changes as more Immigration branches are found |
| Celery | Runs scraping and re-embedding off the request path |
| Redis | Celery broker, and plan cache keyed on case signature |

### Data

| Technology | Why |
|---|---|
| PostgreSQL 16 | Rules, conditions, versions and cases are all relational |
| pgvector | Embeddings for free-text situation matching, in the same database rather than a separate vector store |
| Cloudflare R2 / S3 | Raw page snapshots — this is what makes the audit trail real |

### Ingestion and AI

| Technology | Why |
|---|---|
| httpx + BeautifulSoup | Immigration pages are plain HTML, no headless browser needed |
| pdfplumber | Their instruction documents are PDFs |
| Claude API | Two narrow jobs only: parsing scraped text into structured rules, and mapping free-text situations to a service. Never answers citizens directly |
| sentence-transformers | Local embeddings, no per-call cost, no GPU required at this scale |

### Infrastructure

| Technology | Why |
|---|---|
| Docker Compose | Postgres, Redis and the API come up with one command |
| Railway | Free tier, deploys from GitHub, managed Postgres and Redis |
| Nginx | Rate limiting at the edge, protecting LLM-backed endpoints |
| OpenTelemetry + Jaeger | Trace a request from intake through rule evaluation to source document |

### Quality

| Technology | Why |
|---|---|
| pytest | Rules engine unit tests — branching logic regresses silently |
| Schemathesis | Property tests against the OpenAPI schema |
| Jest + React Native Testing Library | Component tests |
| GitHub Actions | Runs tests and the grounding eval on every push |
| Ruff | Lint and format, one tool |
| OpenSpec | Spec-driven development — every change is proposed before it's implemented |

---

## Why each infrastructure component exists

Each of these answers to a real constraint, not to a checklist.

**Load balancing** — passport demand is spiky and seasonal (school holidays, pre-migration
rushes). Horizontal scaling absorbs that without over-provisioning year-round.

**Rate limiting** — the free-text intake calls an LLM, which costs money per request.
Uncapped, a single script drains the budget.

**Queue** — scraping and re-embedding take minutes. They cannot happen inside a citizen's
request.

**Caching** — a handful of case shapes are most of the traffic. An adult renewal with no
name change in Colombo resolves identically for thousands of people.

**Three kinds of storage** — PostgreSQL holds structured rules; pgvector holds embeddings
for free-text search; object storage holds raw page snapshots, which is what lets you prove
a rule came from a real document on a real date.

**Auth** — JWT on the admin console only. Approving a rule change alters what thousands of
citizens are told to do; that action needs an identity attached. Citizens need no account.

**Tracing** — when a plan is wrong, you must be able to answer "which rule version and which
source document produced this line."

---

## Project structure

```
govassist/              React Native mobile app
  src/
    components/         Reusable primitives
    screens/            Full screens
    navigation/         React Navigation stack
    theme/              tokens.ts — single source of truth for design values
    api/                Backend client
    store/              Zustand stores

api/                    FastAPI backend
  app/
    scraper/            immigration.gov.lk scraper
    ingestion/          PDF extraction and rule parsing
    engine/             Condition evaluator and requirement resolver
    models/             SQLAlchemy models
    db/                 Database session and migrations
    mcp/                MCP server tools
    api/                FastAPI routes

openspec/               Change proposals and specs
```

---

## Getting started

### Prerequisites

- Node.js 20.19+
- Python 3.12
- Docker Desktop
- Expo Go on a physical device

### Mobile app

```bash
cd govassist
npm install
cp .env.example .env    # then set EXPO_PUBLIC_API_BASE_URL — see "Running on a physical device" below
npx expo start --clear
```

Scan the QR code with Expo Go.

### Backend

```bash
docker compose up -d

cd api
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --reload
```

API docs at `http://localhost:8000/docs`

### Running on a physical device (LAN setup)

The app has to reach the backend over your local network — `localhost`
in the mobile app's `.env` resolves to the *phone*, not your laptop, so
it will silently fail to connect. Two things have to line up:

1. **The backend must bind to `0.0.0.0`, not just `127.0.0.1`.** The
   `--host 0.0.0.0` flag above is required — without it, uvicorn only
   accepts connections from the machine it's running on, and the phone
   can't reach it at all, even on the same Wi-Fi.
2. **The mobile app needs your laptop's LAN IP**, not `localhost`, in
   `EXPO_PUBLIC_API_BASE_URL`.
   - **Windows**: run `ipconfig`, find the active adapter (usually
     "Wireless LAN adapter Wi-Fi"), and use its `IPv4 Address` (e.g.
     `192.168.1.42`).
   - **macOS**: System Settings → Wi-Fi → Details → look for the IP
     address, or run `ipconfig getifaddr en0` in a terminal.
   - **Linux**: `hostname -I` or `ip addr show`.

   Set `EXPO_PUBLIC_API_BASE_URL=http://<that-ip>:8000` in the mobile
   app's `.env`, then restart `expo start`. Your phone and laptop must
   be on the same Wi-Fi network.

If the app can't reach the backend at all — a wrong IP, the backend not
running, or a firewall blocking the port — the app shows a distinct
"can't reach the server" message with a retry button, not a silent hang.

---

## Development workflow

This project uses [OpenSpec](https://openspec.dev) for spec-driven development.
Every change starts as a proposal before any code is written.

```bash
/opsx:propose "your change idea"
```

Proposals live in `openspec/changes/` as plain Markdown, so they're reviewable in
a pull request like any other file.

---

## Design system

All colours, spacing, radii and font sizes come from `govassist/src/theme/tokens.ts`.
Nothing is hardcoded.

Key constraints, driven by the users — Sri Lankan citizens including older and less
technical people, often anxious about a government process and using the app outdoors:

- Minimum touch target 48px
- Minimum body font size 16px
- High contrast, generous spacing
- Plain language, no jargon

---

## Content rules

- Every requirement shown to a user carries its source and a verified-as-of date
- No fee, document or deadline is ever stated without a verified source
- The app gives guidance, not an official ruling, and says so where it matters
- A wrong checklist is worse than no checklist

---

## Out of scope

- Sinhala and Tamil (English only for this build)
- Online submission or payment — this guides preparation, it does not transact
- Appointment booking
- Citizen accounts (device storage only; optional Google sign-in for cross-device sync)

---

## Status

Active development. Built for the Ascentic AI Launch Pad.
