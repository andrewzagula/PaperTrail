# Papertrail — CLAUDE.md

## What Is This Project

Papertrail is a self-hosted, open-source AI research copilot. Users upload research papers (arXiv link or PDF), and the app provides structured breakdowns, section-aware Q&A, multi-paper comparison, idea generation, and code implementation from papers.

**Distribution:** Self-hosted, single-user. No accounts, no cloud, no Docker. Users bring their own OpenAI API key. All data persists locally in `data/`.

**Status:** MVP in progress. See `PROGRESS.md` for full phase breakdown, current status, and detailed plans for each phase.

---

## Quick Start (Dev)

```bash
# Backend
cd backend
pip install -r requirements.txt
cd ..
cp .env.example .env          # set OPENAI_API_KEY
python run.py                  # starts FastAPI on :8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                    # starts Next.js on :3000
```

Backend must be running for frontend to work (API calls go to localhost:8000).

---

## Project Structure

```
PaperTrail/
├── CLAUDE.md                # This file
├── PROGRESS.md              # Detailed phase tracker — READ THIS FIRST
├── run.py                   # Backend entry point
├── .env.example             # Only needs OPENAI_API_KEY
├── data/                    # Runtime data (gitignored)
│   ├── papertrail.db        # SQLite database
│   ├── pdfs/                # Downloaded/uploaded PDFs
│   └── chroma/              # ChromaDB vector storage
├── backend/                 # Python/FastAPI
│   ├── requirements.txt
│   └── app/
│       ├── main.py          # App entry + router registration
│       ├── config.py        # Settings (pydantic-settings, reads ../.env)
│       ├── database.py      # SQLAlchemy engine + session (SQLite)
│       ├── models/
│       │   └── models.py    # All ORM models (User, Paper, PaperSection, Chat, SavedItem)
│       ├── routers/
│       │   └── papers.py    # Paper CRUD + ingestion endpoints
│       └── services/
│           ├── vector_store.py      # ChromaDB wrapper
│           ├── arxiv_fetcher.py     # arXiv URL parsing + PDF download
│           ├── pdf_parser.py        # PyMuPDF text extraction
│           ├── section_splitter.py  # Heading detection + section splitting
│           └── embedder.py          # Chunking + OpenAI embeddings
├── frontend/                # Next.js (App Router)
│   ├── src/app/
│   │   ├── layout.tsx       # Root layout
│   │   ├── page.tsx         # Home page (paper list + upload link)
│   │   ├── globals.css      # Tailwind + CSS variables (light/dark mode)
│   │   └── papers/
│   │       ├── new/page.tsx     # Upload page
│   │       └── [id]/page.tsx    # Paper view page
│   └── next.config.ts       # Proxies /api/* → localhost:8000
```

---

## Tech Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v4 | All pages are `"use client"` components |
| Backend | Python, FastAPI | Async endpoints for ingestion, sync for reads |
| Database | SQLite via SQLAlchemy 2.0 | Auto-created on startup via `Base.metadata.create_all()` |
| Vector Store | ChromaDB (embedded, persistent) | Stored in `data/chroma/`, cosine similarity |
| AI | OpenAI API (`openai` Python SDK) | `text-embedding-3-small` for embeddings, GPT-4o-mini/GPT-4o for generation |
| Orchestration | LangChain + LangGraph | Not yet used — planned for Phase 4+ (compare, ideas, code gen) |

---

## Coding Patterns & Conventions

### Backend

- **Router pattern:** Each feature domain gets its own router file in `app/routers/`. Register in `main.py` via `app.include_router(router)`.
- **Service pattern:** Business logic lives in `app/services/`. Routers call services, services call external APIs or the database.
- **DB sessions:** Use `db: Session = Depends(get_db)` in endpoint parameters. The `get_db` dependency yields a session and auto-closes.
- **UUID handling:** SQLAlchemy stores UUIDs as `Uuid` type. When querying by ID from a URL path parameter (string), convert with `uuid.UUID(paper_id)` first — SQLite's Uuid type requires actual UUID objects, not strings.
- **Default user:** Single-user mode uses a default user with email `local@papertrail.dev`. Created on first API call via `_get_or_create_default_user(db)` in the papers router. All new routers that need a user should follow this pattern.
- **Pydantic schemas:** Request/response models defined at the top of each router file. Use `class Config: from_attributes = True` for ORM compatibility.
- **Error handling:** Use `raise HTTPException(status_code=..., detail=...)`. OpenAI/embedding failures should be caught and logged, not crash the request (see `_store_paper` in papers.py for the pattern).
- **Config:** All settings in `app/config.py` via `pydantic-settings`. Access as `from app.config import settings`. The `.env` file lives at project root (not in `backend/`).

### Frontend

- **All pages are client components** (`"use client"`) — no server components yet.
- **API URL:** `const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"` at the top of each page. Fetch directly from the FastAPI backend.
- **Styling:** Tailwind utility classes only. Theme colors use CSS variables defined in `globals.css`: `--background`, `--foreground`, `--primary`, `--primary-hover`, `--muted`, `--border`, `--card`. Reference as `text-[var(--muted)]`, `bg-[var(--card)]`, etc. Supports light/dark mode via `prefers-color-scheme`.
- **No component library.** All UI is hand-built with Tailwind. No shadcn, no Material UI.
- **Routing:** Next.js App Router. Pages at `src/app/<route>/page.tsx`. Dynamic routes use `[param]` folders.
- **State:** Local `useState`/`useEffect` only. No global state management (Redux, Zustand, etc.).
- **Navigation:** `useRouter()` from `next/navigation` for programmatic navigation. `<a href="...">` for simple links.

### Data Flow

```
Frontend (fetch) → FastAPI backend → SQLite (relational data)
                                   → ChromaDB (vector embeddings)
                                   → OpenAI API (LLM calls)
```

### Dual Storage for Sections

Paper sections exist in both SQLite and ChromaDB:
- **SQLite (`paper_sections` table):** Section text, title, order, relational links
- **ChromaDB (`paper_sections` collection):** Embedding vectors + document text, keyed by `{section_id}_chunk_{i}`

ChromaDB entries have metadata: `{"paper_id": "...", "section_id": "...", "section_title": "...", "chunk_index": 0}`. Filter by `paper_id` when doing RAG retrieval for a specific paper.

---

## Database Schema

5 tables, all with UUID primary keys:

- **users** — id, email, name, created_at
- **papers** — id, user_id (FK), title, authors, abstract, arxiv_url, pdf_path, raw_text, structured_breakdown (JSON), created_at
- **paper_sections** — id, paper_id (FK, CASCADE), section_title, section_order, content, chunk_index, created_at
- **chats** — id, user_id (FK), paper_id (FK), role ("user"/"assistant"), content, citations (JSON), created_at
- **saved_items** — id, user_id (FK), item_type ("comparison"/"idea"/"implementation"), title, data (JSON), paper_ids (JSON), created_at

Indexes on all foreign keys + `chats.created_at` + `saved_items.item_type`.

---

## Existing API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/papers/ingest/arxiv` | Ingest paper from arXiv URL. Body: `{"arxiv_url": "..."}` |
| POST | `/papers/ingest/pdf` | Ingest paper from PDF upload. Multipart form with `file` field |
| GET | `/papers/` | List all papers for the default user |
| GET | `/papers/{paper_id}` | Get paper with all sections |
| DELETE | `/papers/{paper_id}` | Delete paper + ChromaDB embeddings |

---

## Verification Commands

```bash
# Backend health check
curl http://localhost:8000/health

# List papers
curl http://localhost:8000/papers/

# Ingest from arXiv
curl -X POST http://localhost:8000/papers/ingest/arxiv \
  -H "Content-Type: application/json" \
  -d '{"arxiv_url": "https://arxiv.org/abs/2301.08745"}'

# Frontend build check
cd frontend && npx next build

# Backend import check
cd backend && python -c "from app.main import app; print('OK')"
```

---

## Adding a New Feature (Checklist)

When building a new phase, follow this pattern:

1. **Read `PROGRESS.md`** for the current phase's planned tasks and context
2. **Backend service** — Create `app/services/<feature>.py` with business logic
3. **Backend router** — Create `app/routers/<feature>.py` with endpoints. Register in `main.py`
4. **Frontend page** — Create `src/app/<route>/page.tsx`. Use `"use client"`, fetch from API_URL, follow existing styling patterns
5. **Test** — Verify backend starts, endpoints return correct data, frontend builds
6. **Update `PROGRESS.md`** — Mark tasks complete, add files to structure, update changelog

---

## Known Gotchas

- **UUID queries on SQLite:** Must convert string IDs to `uuid.UUID()` before querying. SQLAlchemy's `Uuid` type on SQLite doesn't auto-coerce strings.
- **Embedding failures are non-fatal:** If the OpenAI key is missing/invalid, papers still save — embeddings are skipped. Check `num_chunks_embedded` in the ingestion response.
- **Section splitter heuristics:** Uses regex heading detection with a 30+ heading dictionary. Works well on standard academic papers. May produce poor results on non-standard formats (slides, theses, books).
- **No auth:** There is no authentication. A default user (`local@papertrail.dev`) is auto-created. All data belongs to this single user.
- **CORS:** Backend allows `http://localhost:3000` by default. If the frontend runs on a different port, update `BACKEND_CORS_ORIGINS` in `.env`.
- **`data/` directory:** Auto-created at runtime by `config.py`. Gitignored. Contains all persistent state. Deleting it resets everything.
- **Tailwind v4:** Uses `@import "tailwindcss"` syntax (not `@tailwind` directives). PostCSS plugin is `@tailwindcss/postcss` (not `tailwindcss`). No `tailwind.config.ts` file — config is in CSS.

---

## What NOT to Build (MVP Scope)

These are explicitly deferred per the PRD:
- Research graph / citation graph
- Autonomous agents
- Complex memory systems
- Image/figure parsing
- Notes / annotations
- Tagging system
- Paper search / recommendation
- Hosted/cloud version
- Multi-user / authentication
- Mobile responsiveness
