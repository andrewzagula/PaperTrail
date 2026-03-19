# PaperTrail

**Self-hosted AI research copilot.** Upload papers, get structured breakdowns, ask section-aware questions, compare across papers, generate ideas, and turn methods into code.

Unlike generic "chat with PDF" tools, PaperTrail understands academic paper structure — sections, methodology, contributions, limitations — and uses that structure to give you better answers.

> **No accounts. No cloud. No Docker.** Bring your own OpenAI API key, and everything runs locally.

## Features

- **Paper ingestion** — paste an arXiv link or upload a PDF. Text is extracted, sections are detected, and embeddings are generated automatically
- **Structured breakdown** — problem, method, key contributions, results, limitations, future work *(coming soon)*
- **Section-aware Q&A** — ask grounded questions with citations back to specific sections *(coming soon)*
- **Multi-paper comparison** — select 2-5 papers and get a structured comparison table *(coming soon)*
- **Idea generation** — generate novel research ideas using structured transformations *(coming soon)*
- **Paper to code** — turn methods into pseudocode and Python/PyTorch starter code *(coming soon)*

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
# Terminal 1 — backend
python run.py
# API at http://localhost:8000
```

```bash
# Terminal 2 — frontend
cd frontend && npm run dev
# App at http://localhost:3000
```

Open **http://localhost:3000** and start uploading papers.

## How It Works

1. Paste an arXiv URL or drag-and-drop a PDF
2. PaperTrail extracts text, detects sections, and generates vector embeddings
3. You get a structured, navigable view of the paper
4. Ask questions, compare papers, generate ideas, get starter code *(coming soon)*

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4 |
| Backend | Python, FastAPI |
| Database | SQLite (zero config) |
| Vector Store | ChromaDB (embedded, persistent) |
| AI | OpenAI API (embeddings + generation) |

No Docker. No external database. Everything runs on your machine.

## Data Storage

All data lives in `data/` (auto-created on first run):

| Path | Contents |
|---|---|
| `data/papertrail.db` | SQLite database (papers, sections, chats) |
| `data/pdfs/` | Downloaded and uploaded PDF files |
| `data/chroma/` | Vector embeddings for semantic search |

To reset everything, delete the `data/` directory.

## Troubleshooting

**Backend won't start** — make sure you've installed dependencies (`pip install -r backend/requirements.txt`) and set `OPENAI_API_KEY` in `.env`.

**Frontend can't reach backend** — the backend must be running on port 8000. Check CORS if you changed the frontend port (set `BACKEND_CORS_ORIGINS` in `.env`).

**Embeddings fail but paper still saves** — this is by design. If your API key is invalid or rate-limited, the paper saves without embeddings. Check the `num_chunks_embedded` field in the API response.

## Roadmap

| Feature | Status |
|---|---|
| Paper Ingestion (arXiv + PDF) | Done |
| Structured Breakdown | In Progress |
| Section-Aware Chat | Planned |
| Multi-Paper Comparison | Planned |
| Idea Generation | Planned |
| Paper to Code | Planned |

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
