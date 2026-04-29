# PaperTrail

PaperTrail is a self-hosted research workspace for finding, reading, comparing, and extending arXiv papers with help from an LLM provider you choose.

It is built for a single local user. There are no hosted accounts, no required cloud database, and no required Docker setup. Runtime state lives on your machine in SQLite, local PDF files, and a local ChromaDB vector store.

> Project status: pre-1.0. The core local workflows are implemented, but the app is still evolving and should be treated as an experimental research tool.

## What PaperTrail Does

- Starts from a plain-language research question.
- Generates targeted arXiv search queries.
- Searches arXiv, deduplicates results, and ranks papers by relevance.
- Ingests papers from arXiv links, discovery results, or uploaded PDFs.
- Extracts PDF text and sections for browsing, analysis, and retrieval.
- Produces structured paper breakdowns covering problem, method, results, limitations, contributions, and future work.
- Supports grounded chat over an ingested paper using section retrieval.
- Compares multiple saved papers with normalized profiles, a comparison table, warnings, and a narrative summary.
- Generates follow-on research ideas from papers or a topic.
- Turns a paper into an implementation-oriented plan with algorithm steps, pseudocode, assumptions, setup notes, tests, and starter code.
- Saves comparisons, ideas, and implementation plans into a local workspace.

## What It Is Not

PaperTrail is intentionally bounded:

- It searches arXiv only.
- It does not browse the open web.
- It does not autonomously follow citation chains.
- It does not run open-ended multi-step research loops without user action.
- It does not provide multi-user auth, hosted sync, or collaboration features.
- It is not a replacement for reading the source paper.

The goal is a focused local research assistant, not an autonomous research agent.

## Tech Stack

| Area | Technology |
| --- | --- |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4 |
| Backend | Python 3.11+, FastAPI, SQLAlchemy |
| Database | SQLite |
| Vector store | ChromaDB |
| PDF parsing | PyMuPDF |
| LLM orchestration | Provider abstraction over OpenAI, Anthropic, Gemini, OpenAI-compatible APIs, and Ollama |
| Embeddings | OpenAI embeddings or local sentence-transformers |
| Paper source | arXiv API |

## Requirements

- Python 3.11+
- Node.js 18+
- One supported chat and structured-output provider:
  - OpenAI
  - Anthropic
  - Gemini
  - OpenAI-compatible API endpoint
  - Ollama
- One supported embedding provider:
  - OpenAI embeddings
  - sentence-transformers running locally

Hosted LLM providers receive the prompts and paper excerpts required for the workflow you run. Use Ollama and local sentence-transformers if you need a fully local model path.

## Quick Start

```bash
git clone https://github.com/andrewzagula/PaperTrail.git
cd PaperTrail
```

Create and configure the backend environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
```

Edit `.env` for the provider you want to use. For the default OpenAI setup, set:

```bash
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
```

Install frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

Start the backend:

```bash
python run.py
```

Start the frontend in another terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`.

The API will be available at `http://localhost:8000`, with FastAPI docs at `http://localhost:8000/docs`.

## Configuration

PaperTrail reads backend configuration from `.env` in the repository root. Start from `.env.example`.

### Provider Selection

| Variable | Purpose |
| --- | --- |
| `LLM_PROVIDER` | Chat and structured-output provider: `openai`, `anthropic`, `gemini`, `openai_compatible`, or `ollama` |
| `LLM_MODEL` | Default chat model for the selected provider |
| `EMBEDDING_PROVIDER` | Embedding provider: `openai` or `sentence_transformers` |
| `EMBEDDING_MODEL` | Embedding model for the selected embedding provider |

### Provider Credentials

| Provider | Required variables |
| --- | --- |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Gemini | `GOOGLE_API_KEY` |
| OpenAI-compatible | `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_BASE_URL` |
| Ollama | `OLLAMA_BASE_URL` |
| Local embeddings | `LOCAL_EMBEDDING_DEVICE` is optional |

`OPENAI_BASE_URL` is optional for OpenAI-native compatible transport overrides.

### Per-Workflow Models

These variables let you tune cost, speed, or quality without changing code:

- `DISCOVERY_QUERY_MODEL`
- `DISCOVERY_RANK_MODEL`
- `ANALYSIS_MODEL`
- `CHAT_MODEL`
- `COMPARE_PROFILE_MODEL`
- `COMPARE_SYNTHESIS_MODEL`
- `IDEA_GENERATION_MODEL`
- `IDEA_CRITIQUE_MODEL`
- `IMPLEMENTATION_EXTRACTION_MODEL`
- `IMPLEMENTATION_CODE_MODEL`
- `IMPLEMENTATION_REVIEW_MODEL`

The frontend uses `NEXT_PUBLIC_API_URL` when set. Otherwise it defaults to `http://localhost:8000`.

## Embeddings

PaperTrail stores retrieval embeddings in ChromaDB collections namespaced by embedding provider and model. Switching `EMBEDDING_PROVIDER` or `EMBEDDING_MODEL` does not mix vector spaces.

Existing papers are not automatically re-embedded after an embedding backend change. Paper responses include the active-backend embedding status:

- `ready`
- `stale`
- `missing`
- `failed`

Rebuild embeddings with:

```bash
# One paper
curl -X POST http://localhost:8000/papers/<paper_id>/reembed

# All papers not ready for the active embedding backend
curl -X POST http://localhost:8000/papers/reembed \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
```

## Local Data

Runtime data is created under `data/` and is ignored by Git.

| Path | Purpose |
| --- | --- |
| `data/papertrail.db` | SQLite database |
| `data/pdfs/` | Downloaded and uploaded PDFs |
| `data/chroma/` | ChromaDB vector collections |

Delete `data/` to reset your local workspace.

## Main API Surface

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Backend health check |
| `POST /discover/` | Start an arXiv discovery run |
| `GET /discover/` | List discovery runs |
| `GET /discover/{run_id}` | Fetch one discovery run and ranked results |
| `POST /discover/{run_id}/ingest/{result_id}` | Ingest a discovery result |
| `POST /papers/ingest/arxiv` | Ingest a paper from an arXiv URL or ID |
| `POST /papers/ingest/pdf` | Upload and ingest a PDF |
| `GET /papers/` | List ingested papers |
| `GET /papers/{paper_id}` | Fetch paper metadata, sections, and analysis state |
| `POST /papers/{paper_id}/analyze` | Generate a structured breakdown |
| `POST /papers/{paper_id}/chat` | Ask a grounded question about one paper |
| `POST /papers/compare` | Compare selected papers |
| `POST /papers/ideas` | Generate research ideas |
| `POST /papers/{paper_id}/implement` | Generate an implementation plan |
| `GET /workspace/summary` | Fetch dashboard summary data |
| `GET /workspace/saved-items` | List saved comparisons, ideas, and implementation plans |

See `http://localhost:8000/docs` for the full generated OpenAPI reference.

## Project Layout

```text
PaperTrail/
├── backend/
│   ├── app/
│   │   ├── llm/          # Provider abstraction and clients
│   │   ├── models/       # SQLAlchemy models
│   │   ├── routers/      # FastAPI routes
│   │   ├── services/     # PDF, arXiv, RAG, comparison, ideas, implementation
│   │   └── workflows/    # LangGraph-style workflow helpers
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/app/          # Next.js app routes
│   ├── src/lib/
│   └── package.json
├── data/                 # Local runtime state, gitignored
├── .env.example
├── run.py                # Backend dev entry point
└── README.md
```

## Development

Run the backend directly:

```bash
source .venv/bin/activate
python run.py
```

Run the frontend:

```bash
cd frontend
npm run dev
```

Run backend tests:

```bash
pytest backend/tests -q
```

Run only live provider smoke tests:

```bash
pytest backend/tests/test_llm_live_smoke.py -q
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Contributing

Contributions are welcome. The most useful issues and pull requests are scoped to one workflow or one layer of the stack.

Good first areas:

- Provider compatibility fixes
- Retrieval and citation quality improvements
- PDF parsing edge cases
- Tests for discovery, comparison, ideas, and implementation workflows
- Frontend usability and accessibility improvements
- Documentation for local model setups

Before opening a pull request:

1. Run `pytest backend/tests -q`.
2. Run `cd frontend && npm run build`.
3. Keep local data, generated PDFs, Chroma files, `.env`, and caches out of Git.
4. Describe which provider and embedding backend you tested with.

## Security and Privacy

- Do not commit `.env`, provider keys, local PDFs, Chroma data, or SQLite data.
- The default app has a single local user record and no authentication layer.
- Hosted model providers receive paper text excerpts and prompts for workflows you run through that provider.
- The project does not add its own telemetry.

If you find a security issue, please avoid posting sensitive details publicly in an issue. Contact the maintainer privately if possible, or open a minimal issue requesting a security contact.

## License

PaperTrail is released under the [MIT License](LICENSE).
