# Papertrail — Project Progress & Status

> **Last Updated:** 2026-03-18
> **Current Phase:** Phase 2 — Structured Paper Breakdown (NEXT UP)
> **Owner:** Andrew Zagula
> **Product:** AI Research Workflow Tool (MVP / V0)

---

## Overall Vision

Papertrail is a research copilot that supports the **full research workflow**:
**Paper → Understanding → Comparison → Idea → Implementation**

Unlike generic "AI PDF chat" tools, Papertrail provides structured breakdowns, cross-paper reasoning, idea generation, and code implementation from papers.

### Distribution Model

**Self-hosted, open-source, single-user.** Users clone the repo, add their own OpenAI API key, and run it locally. No accounts, no hosted service, no Docker required. All data (SQLite database + ChromaDB vectors) persists in a local `data/` directory.

---

## MVP Definition of Done

A user can:
- [x] Upload a paper (arXiv link or PDF)
- [ ] Understand it clearly (structured breakdown)
- [ ] Ask grounded questions about it (section-aware RAG chat)
- [ ] Compare it with other papers (multi-paper comparison table)
- [ ] Generate research ideas from papers
- [ ] Get a usable implementation plan + starter code

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router), React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Database | SQLite (via SQLAlchemy) — zero-config, file-based |
| Vector Store | ChromaDB (embedded, persistent) — no server needed |
| AI/LLM | OpenAI API (GPT-4o / GPT-4o-mini) |
| Orchestration | LangChain (embeddings, retrieval), LangGraph (compare, ideas, code gen) |

### Why SQLite + ChromaDB (not Postgres + pgvector)

This is a self-hosted, single-user tool. SQLite and ChromaDB are both embedded — no database servers to install, configure, or manage. The entire data layer is just files on disk inside `data/`. This means:
- **Zero infrastructure** — no Docker, no Postgres, no port conflicts
- **5-minute setup** — clone, install, set API key, run
- **Portable** — back up or delete the `data/` directory, that's it

If the project ever needs a hosted multi-user version, Postgres can be added as an alternative backend (SQLAlchemy abstracts the DB layer, so the switch is a config change).

---

## How to Run

```bash
git clone <repo-url>
cd PaperTrail
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
cp .env.example .env                   # then set OPENAI_API_KEY
python run.py                          # starts backend on http://localhost:8000
# In a second terminal:
cd frontend && npm run dev             # starts frontend on http://localhost:3000
```

---

## Phase Overview

| Phase | Name | Status | Description |
|---|---|---|---|
| **0** | Project Scaffolding | **COMPLETE** | Repo setup, frontend/backend init, SQLite + ChromaDB, models |
| **1** | Paper Ingestion | **COMPLETE** | arXiv/PDF upload, parsing, section extraction, embedding |
| **2** | Structured Breakdown | **NEXT UP** | LLM-generated structured analysis (Problem, Method, etc.) |
| **3** | Section-Aware Chat | NOT STARTED | Grounded RAG Q&A with citations |
| **4** | Multi-Paper Compare | NOT STARTED | Comparison tables + summaries for 2–5 papers |
| **5** | Idea Generation | NOT STARTED | Structured research idea generation (combine, ablate, extend) |
| **6** | Paper → Implementation | NOT STARTED | Algorithm extraction, pseudocode, starter code gen |
| **7** | User Workspace | NOT STARTED | Saved papers/comparisons/ideas, dashboard (no auth — single-user) |
| **8** | Polish & Integration | NOT STARTED | Error handling, loading states, hallucination guardrails |

---

## Phase 0 — Project Scaffolding (COMPLETE)

### Goal
Set up the full project structure so that any developer can clone the repo, install deps, and have a working dev environment with both frontend and backend running. No Docker, no external database servers.

### Tasks

- [x] Create project directory structure
- [x] Initialize Next.js frontend (App Router, TypeScript, Tailwind CSS v4)
- [x] Initialize FastAPI backend with dependency management
- [x] Define database schema (users, papers, paper_sections, chats, saved_items)
- [x] Create SQLAlchemy models with SQLite-compatible types
- [x] Add indexes on all foreign keys and common query columns
- [x] Set up auto-table-creation on startup (`Base.metadata.create_all`)
- [x] Create ChromaDB vector store service (`app/services/vector_store.py`)
- [x] Create `.env.example` (only requires `OPENAI_API_KEY`)
- [x] Create backend config module that reads from `.env`
- [x] Create `run.py` — single entry point for the backend
- [x] Create basic FastAPI app with health check endpoint + lifespan startup
- [x] Create basic Next.js landing/home page
- [x] Create `.gitignore` (excludes `data/`, `.env`, `node_modules`, etc.)
- [x] Verify frontend builds successfully
- [x] Verify backend starts and health check returns OK
- [x] Verify SQLite DB auto-creates in `data/papertrail.db`
- [x] Verify ChromaDB collection initializes in `data/chroma/`

### Architecture Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| Database | SQLite (via SQLAlchemy) | Zero config, embedded, perfect for single-user self-hosted tool |
| Vector Store | ChromaDB (embedded, persistent) | No server needed, pip install, HNSW index built-in |
| PDF Parsing | PyMuPDF (`fitz`) | Fast, lightweight, good text extraction |
| LLM — Chat/Summaries | GPT-4o-mini | Cost-effective for high-frequency calls |
| LLM — Compare/Ideas/Code | GPT-4o | Higher quality needed for complex reasoning |
| Auth | None (single-user) | Self-hosted tool, no login needed. Default user created automatically |
| Deployment | Self-hosted only | Users run locally, bring their own OpenAI key |
| Schema Migrations | `create_all()` on startup | Alembic is overkill for single-user SQLite; tables created automatically |
| LangGraph Usage | Selective (compare, ideas, code gen only) | Avoid over-engineering simpler workflows |

### File Structure

```
PaperTrail/
├── PROGRESS.md                          # This file — project status tracker
├── run.py                               # Single entry point for backend
├── .env.example                         # Only needs OPENAI_API_KEY
├── .gitignore
├── data/                                # Auto-created at runtime (gitignored)
│   ├── papertrail.db                    # SQLite database
│   ├── pdfs/                            # Downloaded/uploaded PDFs
│   └── chroma/                          # ChromaDB persistent storage
├── frontend/
│   ├── package.json
│   ├── next.config.ts                   # Proxies /api/* to FastAPI backend
│   ├── postcss.config.mjs
│   ├── tsconfig.json
│   └── src/
│       └── app/
│           ├── layout.tsx               # Root layout + metadata
│           ├── page.tsx                 # Home — feature cards + paper list
│           ├── globals.css              # Tailwind imports + CSS variables (light/dark)
│           └── papers/
│               ├── new/
│               │   └── page.tsx         # Upload page (arXiv URL + PDF drop zone)
│               └── [id]/
│                   └── page.tsx         # Paper view (header + section nav + content)
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                      # FastAPI app with lifespan + router registration
│       ├── config.py                    # Settings via pydantic-settings, reads .env
│       ├── database.py                  # SQLAlchemy engine + session (SQLite)
│       ├── models/
│       │   └── models.py               # User, Paper, PaperSection, Chat, SavedItem
│       ├── routers/
│       │   └── papers.py               # Paper CRUD + ingestion endpoints
│       ├── services/
│       │   ├── vector_store.py          # ChromaDB wrapper (add, query, delete)
│       │   ├── arxiv_fetcher.py         # arXiv API + PDF download
│       │   ├── pdf_parser.py            # PyMuPDF text + metadata extraction
│       │   ├── section_splitter.py      # Heading detection + section splitting
│       │   └── embedder.py              # Chunking + OpenAI embeddings
│       └── tests/
```

### Data Storage Architecture

```
Relational data (SQLite)          Vector data (ChromaDB)
┌──────────────────────┐          ┌──────────────────────┐
│ users                │          │ paper_sections       │
│ papers               │          │ collection           │
│ paper_sections       │◄────────►│                      │
│ chats                │ linked   │ - id (matches SQLite)│
│ saved_items          │ by ID    │ - embedding          │
└──────────────────────┘          │ - document text      │
  data/papertrail.db              │ - metadata           │
                                  └──────────────────────┘
                                    data/chroma/
```

Paper sections exist in **both** stores:
- **SQLite** holds the section text, title, order, and relational links (which paper, which user)
- **ChromaDB** holds the embedding vector + document text, keyed by the same section UUID

When doing RAG retrieval: query ChromaDB for similar vectors → get section IDs → join with SQLite for full context.

---

## Phase 1 — Paper Ingestion (COMPLETE)

### Goal
User can paste an arXiv link or upload a PDF. System extracts metadata, splits into sections, generates embeddings, and stores everything in SQLite + ChromaDB.

### What Was Built

1. **arXiv fetcher** (`app/services/arxiv_fetcher.py`)
   - Extracts paper ID from any arXiv URL format (abs, pdf, with/without version)
   - Fetches metadata (title, authors, abstract) from arXiv Atom API
   - Downloads PDF to `data/pdfs/`
   - Handles redirects (arXiv HTTP→HTTPS)

2. **PDF parser** (`app/services/pdf_parser.py`)
   - Extracts full text from PDF using PyMuPDF
   - Extracts metadata (title, authors) from PDF properties

3. **Section splitter** (`app/services/section_splitter.py`)
   - 4 heading detection patterns: numbered (`1. Introduction`), letter-prefixed (`A. Appendix`), ALL CAPS (`INTRODUCTION`), title-case (`Introduction`)
   - Matches against 30+ known section headings
   - Minimum 5-char threshold to avoid false positives from table labels
   - Fallback: splits into Abstract + Body if no headings detected
   - Tested on real arXiv papers — correctly identifies 10+ sections

4. **Embedding pipeline** (`app/services/embedder.py`)
   - Chunks sections into ~2000-char passages with 200-char overlap
   - Breaks on paragraph/sentence boundaries when possible
   - Generates embeddings via OpenAI `text-embedding-3-small`
   - Stores in ChromaDB with paper_id + section_id metadata
   - Batched (100 per API call) for large papers
   - **Graceful degradation**: if OpenAI key is missing, paper still saves without embeddings

5. **API endpoints** (`app/routers/papers.py`)
   - `POST /papers/ingest/arxiv` — ingest from arXiv URL
   - `POST /papers/ingest/pdf` — ingest from PDF upload
   - `GET /papers/` — list all papers
   - `GET /papers/{id}` — get paper with sections
   - `DELETE /papers/{id}` — delete paper + embeddings
   - Default local user auto-created on first request

6. **Frontend — Upload page** (`/papers/new`)
   - arXiv URL text input with submit button
   - Drag-and-drop PDF upload zone + file picker
   - Loading spinner with status text
   - Error display
   - Redirects to paper view on success

7. **Frontend — Paper view** (`/papers/[id]`)
   - Header: title, authors, arXiv link, abstract card
   - Left sidebar: section navigation with active highlighting
   - Main area: all sections as cards with content
   - Click section nav to highlight corresponding card

8. **Frontend — Home page** updated
   - "Upload a Paper" button links to `/papers/new`
   - "Your Papers" section lists previously ingested papers
   - Click paper to navigate to its view

### Key Endpoints
- `POST /papers/ingest/arxiv` — body: `{"arxiv_url": "..."}`
- `POST /papers/ingest/pdf` — multipart form with `file` field
- `GET /papers/` — returns list of papers
- `GET /papers/{paper_id}` — returns paper + sections
- `DELETE /papers/{paper_id}` — deletes paper + ChromaDB embeddings

### Files Added
```
backend/app/routers/__init__.py
backend/app/routers/papers.py          # All paper CRUD endpoints
backend/app/services/arxiv_fetcher.py  # arXiv API + PDF download
backend/app/services/pdf_parser.py     # PyMuPDF text extraction
backend/app/services/section_splitter.py  # Heading detection + splitting
backend/app/services/embedder.py       # Chunking + OpenAI embeddings + ChromaDB storage
frontend/src/app/papers/new/page.tsx   # Upload page
frontend/src/app/papers/[id]/page.tsx  # Paper view page
```

### Files Modified
```
backend/app/main.py                    # Added papers router
frontend/src/app/page.tsx              # Added paper list + upload link
```

### Verified
- arXiv URL parsing + PDF download works
- Section detection produces clean results on real papers
- All API endpoints return correct responses
- Frontend builds cleanly
- Graceful handling when OpenAI key is not set (paper saves, embeddings skipped)

---

## Phase 2 — Structured Paper Breakdown (NEXT UP)

### Goal
For each ingested paper, generate a structured analysis: Problem, Method, Key Contributions, Results, Limitations, Future Work. Display in a clean card-based UI. This is the **key differentiator** — not a generic summary, but a structured decomposition.

### Planned Tasks

1. **Backend — Analysis endpoint** (`POST /papers/{id}/analyze`)
   - Retrieve paper's sections from SQLite
   - Send to OpenAI with structured prompt requesting 6 fields: Problem, Method, Key Contributions, Results, Limitations, Future Work
   - Use OpenAI structured output (JSON mode or function calling) to guarantee response shape
   - Store result in `papers.structured_breakdown` JSON column
   - Return the breakdown

2. **Backend — Analysis service** (`app/services/analyzer.py`)
   - Build prompt from paper sections (fit within context window)
   - Define the structured output schema
   - Handle token limits (truncate if paper is too long)

3. **Frontend — Structured breakdown display** (update `/papers/[id]`)
   - Add a "Breakdown" tab/section above the raw sections
   - 6 cards: Problem, Method, Key Contributions, Results, Limitations, Future Work
   - "Analyze" button to trigger generation if breakdown doesn't exist yet
   - Loading state while analysis runs

### Key Endpoint
- `POST /papers/{id}/analyze` — triggers analysis, returns structured breakdown
- `GET /papers/{id}` — already returns `structured_breakdown` field (currently null)

---

## Phase 3 — Section-Aware Chat (Grounded RAG)

### Goal
User asks questions about a paper; system retrieves relevant sections via vector search and responds with citations.

### Planned Work
- `POST /api/papers/{id}/chat` — RAG endpoint
- Embed query → ChromaDB similarity search (filtered by `paper_id`) → LLM answer with citations
- Store chat history in `chats` table
- Frontend chat panel on paper view page
- Clickable citation tags linking back to sections

---

## Phase 4 — Multi-Paper Compare

### Goal
Select 2–5 papers, get a structured comparison table + narrative summary.

### Planned Work
- `POST /api/papers/compare` — accepts list of paper IDs
- LangGraph workflow: normalize → build comparison matrix → generate summary
- Comparison table: method, dataset, results, strengths, weaknesses
- Frontend compare page (`/compare`) with paper selector + rendered table
- Save comparison to `saved_items`

---

## Phase 5 — Idea Generation

### Goal
Generate 3–5 research ideas using structured transformations (combine, ablate, extend, apply).

### Planned Work
- `POST /api/papers/ideas` — accepts paper IDs or topic
- LLM prompted with explicit transformation strategies
- Each idea: description, why interesting, feasibility (low/med/high)
- Frontend ideas page (`/ideas`) with cards + save buttons

---

## Phase 6 — Paper → Implementation

### Goal
Turn a paper's method into step-by-step algorithm breakdown, pseudocode, missing assumptions, and Python/PyTorch starter code.

### Planned Work
- `POST /api/papers/{id}/implement` — multi-step LLM pipeline
- LangGraph workflow: extract steps → identify gaps → pseudocode → code
- Frontend implementation view (`/papers/[id]/implement`) with tabs
- Syntax-highlighted code blocks with copy button

---

## Phase 7 — User Workspace

### Goal
Persistence layer so users can manage their papers, comparisons, and ideas. No auth — single-user self-hosted tool.

### Planned Work
- Default local user (auto-created on first run)
- Dashboard page (`/dashboard`): My Papers, Saved Comparisons, Saved Ideas
- CRUD endpoints for workspace items
- Note: no login/signup flow needed for self-hosted single-user mode

---

## Phase 8 — Polish & Integration

### Goal
Stability and usability for open-source release.

### Planned Work
- Error handling (bad PDFs, invalid URLs, LLM timeouts)
- Loading states / skeleton UIs for all LLM calls
- Hallucination guardrails (cite-or-abstain, low-confidence warnings)
- Responsive design (laptop-first, not mobile)
- End-to-end manual testing of full workflow
- README with setup instructions, screenshots, and usage guide

---

## What Is NOT In MVP Scope

Per the PRD, these are explicitly deferred:
- Full research graph / citation graph
- Autonomous agents
- Complex memory systems
- Multi-modal parsing (images/figures)
- Perfect code generation
- Notes / annotations system
- Tagging system
- Paper search / recommendation
- Hosted/cloud version
- Multi-user support / authentication

---

## Future Versions (Context)

| Version | Focus | Key Additions |
|---|---|---|
| V1 | Research Workspace | Notes, annotations, collections, tagging, search |
| V2 | Research Graph | Citation graph, concept linking, similar papers, clusters |
| V3 | Advanced Copilot | Lit review generator, contradiction detection, experiment planning |
| V4 | Agentic System | Multi-step agents, autonomous exploration, human-in-the-loop |
| V5 | Execution Layer | Runnable templates, dataset suggestions, training pipelines |

---

## Changelog

| Date | Phase | What Changed |
|---|---|---|
| 2026-03-18 | Phase 0 | Project initialized. Scaffolded frontend (Next.js), backend (FastAPI), Docker Compose, DB schema, models, Alembic migrations. |
| 2026-03-18 | Phase 0 | **Architecture pivot:** Replaced Postgres + pgvector + Docker with SQLite + ChromaDB (embedded). Removed docker-compose.yml and Alembic. Added `run.py` entry point, `vector_store.py` service, auto-table-creation on startup. Simplified `.env.example` to just `OPENAI_API_KEY`. Added indexes on all FK columns. Self-hosted single-user model confirmed. |
| 2026-03-18 | Phase 1 | **Paper ingestion complete.** Built arXiv fetcher, PDF parser, section splitter (4 heading patterns, 30+ known headings), embedding pipeline (chunking + ChromaDB storage), 5 API endpoints, upload page, paper view page with section nav. Tested on real arXiv papers. Graceful degradation when API key is missing. |
