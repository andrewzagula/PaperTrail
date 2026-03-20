# PaperTrail

**Self-hosted AI research assistant for arXiv.** Start with a research question: PaperTrail searches arXiv, ranks papers by relevance, and helps you understand what it finds through structured breakdowns, section-aware Q&A, cross-paper comparison, idea generation, and code extraction.

Unlike generic "chat with PDF" tools, PaperTrail understands academic paper structure, including sections, methodology, contributions, and limitations, and uses that structure to give you better answers. Unlike autonomous research agents, PaperTrail keeps you in control: bounded search budgets, explicit uncertainty, and human-in-the-loop decisions at every step.

> **No accounts. No cloud. No Docker.** Bring your own OpenAI API key, and everything runs locally.

## How It Works

1. **Ask a question**: describe what you're researching in natural language
2. **PaperTrail searches arXiv**: the system generates targeted search queries, fetches results, deduplicates, and ranks them by relevance with explanations *(coming soon)*
3. **Ingest the best matches**: select papers to ingest for deep analysis, or upload your own PDFs directly
4. **Go deep**: structured breakdowns, grounded Q&A, multi-paper comparison, idea generation, and code extraction *(coming soon)*

You can also skip discovery and upload papers directly; arXiv links and PDF uploads are always available.

## Features

| Feature | Status |
|---|---|
| Paper ingestion (arXiv link + PDF upload) | Done |
| Research discovery (question → arXiv search → ranked results) | Planned |
| Structured breakdown (problem, method, contributions, results) | Planned |
| Section-aware Q&A with citations | Planned |
| Multi-paper comparison | Planned |
| Idea generation | Planned |
| Paper to code | Planned |

## What "Agent" Means Here

PaperTrail uses the word "agent" in a specific, bounded sense:

- The system generates search strategies from your question (LLM-assisted)
- It executes those searches against the arXiv API (not the open web)
- It ranks and filters results with explanations (LLM-assisted)
- It does **not** browse the web, follow citation chains autonomously, or take multi-step actions without your approval
- Search budgets are explicit and capped (max queries, max results per query)

This is a tool that helps you search smarter, not an autonomous agent that researches on your behalf.

## Requirements

- Python 3.11+
- Node.js 18+
- An [OpenAI API key](https://platform.openai.com)

## Quick Start

```bash
# Clone and enter the repo
git clone https://github.com/yourusername/papertrail.git
cd papertrail

# Backend setup
pip install -r backend/requirements.txt

# Frontend setup
cd frontend && npm install && cd ..

# Configure your API key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

Then start both servers (two terminals):

```bash
# Terminal 1 - backend
python run.py
# API at http://localhost:8000
```

```bash
# Terminal 2 - frontend
cd frontend && npm run dev
# App at http://localhost:3000
```

Open **http://localhost:3000** and start researching.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4 |
| Backend | Python, FastAPI |
| Database | SQLite (zero config) |
| Vector Store | ChromaDB (embedded, persistent) |
| AI | OpenAI API (embeddings + generation) |
| Discovery | arXiv API (search + metadata) |

No Docker. No external database. Everything runs on your machine.

## Data Storage

All data lives in `data/` (auto-created on first run):

| Path | Contents |
|---|---|
| `data/papertrail.db` | SQLite database (papers, sections, discovery runs, chats) |
| `data/pdfs/` | Downloaded and uploaded PDF files |
| `data/chroma/` | Vector embeddings for semantic search |

To reset everything, delete the `data/` directory.

## Troubleshooting

**Backend won't start**: make sure you've installed dependencies (`pip install -r backend/requirements.txt`) and set `OPENAI_API_KEY` in `.env`.

**Frontend can't reach backend**: the backend must be running on port 8000. Check CORS if you changed the frontend port (set `BACKEND_CORS_ORIGINS` in `.env`).

**Embeddings fail but paper still saves**: this is by design. If your API key is invalid or rate-limited, the paper saves without embeddings. Check the `num_chunks_embedded` field in the API response.

**arXiv search returns no results**: the arXiv API uses keyword matching, not semantic search. Try rephrasing your question with more specific technical terms.

## Contributing

Contributions welcome! The codebase follows standard patterns:

- **Backend:** FastAPI with routers in `backend/app/routers/`, services in `backend/app/services/`, models in `backend/app/models/`
- **Frontend:** Next.js App Router with client components, Tailwind CSS for styling, no component libraries

```bash
# Verify everything works
curl http://localhost:8000/health        # backend health check
cd frontend && npx next build            # frontend build check
```

## License

[MIT](LICENSE)
