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
fee or a required document sends someone on a wasted trip.

## What GovAssist does

You describe your situation — in chat, or by picking a service and answering a
short guided sequence of questions — and the system evaluates it against verified
government rules to produce:

- A personalised document checklist, with a source and verified-as-of date on
  every item
- The exact fee computed for your case, including conditional penalty tiers
  (e.g. a lost/stolen passport's penalty, shown separately from the base fee)
- The specific office (or overseas mission) that accepts your application
- Prerequisites flagged in the order they must happen

Every requirement traces back to a real government document — a scraped page or
PDF, stored with a content hash and fetch timestamp.

## Two kinds of question, two mechanisms

This is the core architectural decision, and it's deliberate:

- **Open questions** ("what's the process for a lost passport?") are answered by
  a tool-using AI agent that calls read-only tools — retrieval, fee lookups,
  office lookups — and composes an answer from what they actually returned.
- **Situation questions** ("I'm 34, my name changed, I'm applying from Kandy —
  what do I need?") are answered by a deterministic **rules engine** that
  evaluates conditions against the citizen's answers. This is what actually
  produces the checklist, fee and office — never the AI.

A general model can describe passport rules in general. It cannot reliably
evaluate ten branching variables against one person's situation and tell you
which government circular said so. The rules engine can, because the rules
live in data (conditions, requirements, fee tiers), not in a paragraph of
plausible-sounding prose.

---

## Scope

**Phase 1 (current)** — Department of Immigration & Emigration, 7 services:
renewal, new applicant, lost or stolen, amendment, under-16, child name
deletion, emergency certificate.

**Phase 2 (later)** — Department for Registration of Persons, Registrar
General's Department, Department of Motor Traffic.

English only for this build.

---

## Architecture

```
Mobile app (Expo)  ──HTTPS──>  FastAPI backend
                                      │
                        ┌─────────────┼─────────────┐
                        │             │             │
                  Rules engine   RAG retrieval   Tool-using
                  (conditions,   (hybrid vector  agent (open
                  fees, offices  + full-text)    questions)
                  as data)             │             │
                        │             │             │
                        └──────┬──────┴─────────────┘
                               │
                    PostgreSQL 16 + pgvector
                    (rules, cases, embeddings —
                     one database, not two stores)
                               │
                    Redis (session cache, Celery broker)
                               │
              Ingestion pipeline ──> immigration.gov.lk scraper
                                  └─> PDF extraction / OCR fallback chain
```

Scraped content never goes live automatically. It creates a **draft** rule
version; only an approved version is ever retrievable or resolvable. That
approval gate is what makes the "verified" claim honest — see
`api/app/seed/` for how the currently-approved rule data was hand-verified
against the department's own pages before being entered.

---

## Tech stack

### Mobile app

| Technology | Version | Why |
|---|---|---|
| React Native + Expo | SDK 54 | Runs on a phone via Expo Go, no native build setup |
| TypeScript (strict) | 5.9 | Intake answers and plan items are typed structures |
| NativeWind | 4.2 (Tailwind 3.4) | Tailwind class names in React Native |
| React Navigation | 7 | Screen stack for services, chat, plan |
| Zustand | 5 | State for the in-progress case and auth |
| Expo SecureStore | — | Device identity and saved plans, no account required |

### Backend

| Technology | Version | Why |
|---|---|---|
| Python | 3.12 | |
| FastAPI | 0.141 | Async, auto-generated OpenAPI docs |
| Pydantic | 2.13 | Validates every payload and rule structure |
| SQLAlchemy + Alembic | 2.0 / 1.19 | Rule schema evolves as more branches are found |
| PostgreSQL + pgvector | 16 | Rules, conditions and embeddings in one database |
| Redis | 7 | Session cache, Celery broker |
| Celery | 5.6 | Scraping and re-embedding off the request path |

### AI orchestration

Six narrow AI jobs, split across two providers by whether the output is
citizen-facing (see `CLAUDE.md`'s "How the LLM APIs are used" for the full
rationale) — routed through a single config-driven gateway, not hardcoded per
call site:

| Technology | Version | Role |
|---|---|---|
| LangGraph | 1.2 | The chat-turn graph: classify → record facts → next question → agent or resolve |
| LiteLLM | 1.98 | Provider gateway — which model serves a job is a config value |
| Anthropic SDK / Claude | — | The one citizen-facing job: the tool-using agent that answers open questions |
| Gemini (free tier) | — | Classification, rephrasing, acknowledgement, OCR fallback — evaluation/presentation work |
| Groq | — | Cross-provider fallback if Gemini is rate-limited |
| sentence-transformers | 5.7 | Local embeddings (all-MiniLM-L6-v2, 384-dim), CPU only |

### Ingestion

| Technology | Why |
|---|---|
| httpx + BeautifulSoup | Scrapes immigration.gov.lk |
| pdfplumber | First-choice PDF text extraction |
| pytesseract + PyMuPDF | Free OCR fallback for scanned PDFs with no text layer |
| Gemini Flash vision | Second free fallback if Tesseract's output fails a quality check |
| Claude (last resort) | Behind a feature flag, only if every free stage fails |

### Quality & observability

| Technology | Why |
|---|---|
| pytest | 65 hand-verified golden scenarios across all 7 services, plus unit/integration tests |
| Langfuse (self-hosted) | LLM call tracing — see `docker-compose.yml` |
| OpenSpec | Every change is proposed (`openspec/changes/`) before it's implemented |

---

## Project structure

```
App.tsx                 Mobile app entry point
src/
  components/            Reusable primitives (Button, Card, ChecklistItem, ...)
  screens/                Full screens (Splash, Login, Departments, Services, Plan)
  navigation/             React Navigation stack
  theme/                  tokens.ts — single source of truth for design values
  api/                    Backend client
  store/                  Zustand stores

api/                      FastAPI backend
  main.py                  App entry point (`uvicorn main:app`)
  app/
    scraper/                immigration.gov.lk scraper
    ingestion/               PDF extraction, OCR fallback chain, rule parsing
    engine/                   Condition evaluator, requirement/fee/office resolvers
    rag/                      Chunk retrieval and grounded answer generation
    chat/                     Intent classification, deterministic intake matcher,
                              tool-using agent, acknowledgement/rephrasing
    graph/                    LangGraph chat-turn orchestration
    auth/                     JWT + bcrypt (item 7 — saved plans)
    llm/                      Provider gateway (LiteLLM)
    models.py                 SQLAlchemy models
    db/                       Database session
    api/                      FastAPI routes
    seed/                     Hand-verified rule data per service
  migrations/               Alembic migrations
  tests/                    pytest suite (golden scenarios, engine, chat, RAG, auth)

openspec/                 Change proposals and specs — every change starts here
```

---

## Getting started

### Prerequisites

- Node.js 20.19+
- Python 3.12
- Docker Desktop
- Expo Go on a physical device (or an iOS/Android simulator)
- API keys: an Anthropic key, a Gemini key (free tier), and a Groq key (free tier) — see `api/.env.example`

### Backend

```bash
docker compose up -d          # Postgres 16 + pgvector, Redis

cd api
python -m venv venv
venv\Scripts\activate         # Windows
source venv/bin/activate      # macOS / Linux
pip install -r requirements.txt

cp .env.example .env          # fill in ANTHROPIC_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, JWT_SECRET_KEY
alembic upgrade head

# Seed the hand-verified rule data for all 7 services (idempotent — safe to re-run)
python -m app.seed.phase4_renewal
python -m app.seed.phase5_approve_documents
python -m app.seed.phase9_new_applicant
python -m app.seed.phase9_lost_stolen
python -m app.seed.phase9_amendment
python -m app.seed.phase9_under_16
python -m app.seed.phase9_child_deletion
python -m app.seed.phase9_emergency_certificate

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API docs at `http://localhost:8000/docs`.

**Note the module path**: the FastAPI app lives in `api/main.py`, so it's
`uvicorn main:app` — not `app.main:app` (`app/` is the Python package holding
routes/engine/etc., not the entry point).

### Mobile app

```bash
npm install
cp .env.example .env    # set EXPO_PUBLIC_API_BASE_URL — see below
npx expo start --clear
```

Scan the QR code with Expo Go.

### Running on a physical device (LAN setup)

The app has to reach the backend over your local network — `localhost` in the
mobile app's `.env` resolves to the *phone*, not your laptop, so it will
silently fail to connect. Two things have to line up:

1. **The backend must bind to `0.0.0.0`, not just `127.0.0.1`.** The
   `--host 0.0.0.0` flag above is required — without it, uvicorn only accepts
   connections from the machine it's running on, and the phone can't reach it
   at all, even on the same Wi-Fi.
2. **The mobile app needs your laptop's LAN IP**, not `localhost`, in
   `EXPO_PUBLIC_API_BASE_URL`.
   - **Windows**: run `ipconfig`, find the active adapter's `IPv4 Address`
     (e.g. `192.168.1.42`).
   - **macOS**: System Settings → Wi-Fi → Details, or `ipconfig getifaddr en0`.
   - **Linux**: `hostname -I` or `ip addr show`.

   Set `EXPO_PUBLIC_API_BASE_URL=http://<that-ip>:8000` in the mobile app's
   `.env`, then restart `expo start`. Your phone and laptop must be on the
   same Wi-Fi network.

If the app can't reach the backend at all — a wrong IP, the backend not
running, or a firewall blocking the port — the app shows a distinct "can't
reach the server" message with a retry button, not a silent hang.

### Running the test suite

```bash
cd api
pytest -q                  # 291 passed, 4 skipped, 38 real-API tests excluded by default
pytest -m real_api         # includes the 38 tests that call a live LLM API
```

---

## Development workflow

This project uses [OpenSpec](https://openspec.dev) for spec-driven development.
Every change starts as a proposal before any code is written:

```bash
/opsx:propose "your change idea"
```

Proposals land in `openspec/changes/` as plain Markdown, reviewable like any
other file.

---

## Design system

All colours, spacing, radii and font sizes come from `src/theme/tokens.ts`.
Nothing is hardcoded.

Key constraints, driven by the users — Sri Lankan citizens including older and
less technical people, often anxious about a government process and using the
app outdoors:

- Minimum touch target 48px
- Minimum body font size 16px
- High contrast, generous spacing
- Plain language, no jargon

---

## Content rules

- Every requirement shown to a citizen carries its source and a
  verified-as-of date
- No fee, document or deadline is ever stated without a verified source
- The app gives guidance, not an official ruling, and says so where it matters
- A wrong checklist is worse than no checklist — when retrieval or the engine
  can't ground an answer, the system says so rather than guessing

---

## Out of scope

- Sinhala and Tamil (English only for this build)
- Online submission or payment — this guides preparation, it does not transact
- Appointment booking
- Citizen accounts beyond device-local storage (optional Google sign-in for
  cross-device sync)

---

## Status

Active development. Built for the Ascentic AI Launch Pad.
