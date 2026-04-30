# PaperTrail

PaperTrail is a self-hosted research workspace for finding, reading, comparing, and extending arXiv papers with help from an LLM provider you choose.

It is built for a single local user. There are no hosted accounts, no required cloud database, and no required Docker setup. Runtime state lives on your machine in SQLite, local PDF files, and a local ChromaDB vector store.

## Features

- Discover and rank relevant arXiv papers from a plain-language research question.
- Ingest arXiv papers or uploaded PDFs into a local searchable workspace.
- Generate structured paper breakdowns and grounded paper chat.
- Compare saved papers and generate follow-on research ideas.
- Create implementation-oriented plans with pseudocode, setup notes, tests, and starter code.

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
- Node.js 18.18+
- Git
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

The shell commands below assume macOS or Linux. On Windows, use the equivalent virtual-environment activation command for your shell.

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
LLM_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
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

Check backend setup state with:

```bash
curl http://localhost:8000/health/details
```

The diagnostics response includes provider names, model names, local data paths, and missing setting names. It does not include API keys.

## Try It

After the backend and frontend are running, this short path exercises the main local workflow.

Recommended papers:

- `1706.03762` - "Attention Is All You Need"
- `1409.0473` - "Neural Machine Translation by Jointly Learning to Align and Translate"

Steps:

1. Start the backend with `python run.py` and the frontend with `cd frontend && npm run dev`.
2. Open `http://localhost:8000/health/details` and confirm the selected LLM and embedding providers are configured. This endpoint reports provider/model names and missing settings only; it does not return API keys.
3. On the home page, search for `attention mechanisms for neural machine translation`.
4. Ingest one or both recommended papers from discovery results. If discovery does not return them, ingest them directly from `/papers/new`.
5. Open a paper page, generate the structured breakdown, and ask a grounded question such as `What problem does self-attention solve in the model?`.
6. Compare the papers from `/compare`, generate ideas from `/ideas`, or create an implementation plan from a paper page.
7. Save generated outputs and reopen them from `/dashboard`.

Hosted providers will receive the prompts and paper excerpts needed for the workflow steps you run. Generated implementation output is starter scaffolding, not verified reproduction code.

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

## API Reference

When the backend is running, open `http://localhost:8000/docs` for the generated OpenAPI reference.

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

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Missing provider API key | Open `http://localhost:8000/health/details`. Set the missing variable in `.env`, then restart `python run.py`. |
| Provider request failed or rate limited | Confirm the provider account has access to the configured model. Try a smaller workflow, wait for rate limits to reset, or switch the relevant per-workflow model variable to a cheaper/faster model. |
| Ollama requests fail | Confirm Ollama is running at `OLLAMA_BASE_URL`, pull the configured model locally, and restart the backend after changing `.env`. |
| Local sentence-transformers fails | Confirm `EMBEDDING_PROVIDER=sentence_transformers`, the Python dependencies installed successfully, and `LOCAL_EMBEDDING_DEVICE` is valid for your machine or left blank. |
| Chat says embeddings are missing, stale, or failed | Rebuild embeddings for one paper with `curl -X POST http://localhost:8000/papers/<paper_id>/reembed`, or rebuild all non-ready papers with `curl -X POST http://localhost:8000/papers/reembed -H "Content-Type: application/json" -d '{"force": false}'`. |
| PDF ingestion fails | Try an arXiv URL first to isolate upload issues. Some PDFs have no extractable text or malformed metadata; PaperTrail needs extractable text for sections and embeddings. |
| arXiv search or PDF download times out | Retry later. PaperTrail depends on the public arXiv API and PDF endpoints, and transient network or service failures can happen. |
| Frontend cannot reach backend | Confirm the backend is running on `http://localhost:8000`. If using a different backend URL, set `NEXT_PUBLIC_API_URL` before starting `npm run dev` or `npm run build`. |

## Contributing

Contributions are welcome. Please keep issues and pull requests focused in scope.

Before opening a pull request:

1. Run `pytest backend/tests -q`.
2. Run `cd frontend && npm run build`.
3. Keep local data, generated PDFs, Chroma files, `.env`, and caches out of Git.
4. Describe which provider and embedding backend you tested with.

## Security and Privacy

- Do not commit `.env`, provider keys, local PDFs, Chroma data, or SQLite data.
- The default app has a single local user record and no authentication layer.
- Do not expose the backend to an untrusted network without adding authentication and deployment hardening.
- Hosted model providers receive paper text excerpts and prompts for workflows you run through that provider.
- The project does not add its own telemetry.

If you find a security issue, please avoid posting sensitive details publicly in an issue. Contact the maintainer privately if possible, or open a minimal issue requesting a security contact.

## License

PaperTrail is released under the [MIT License](LICENSE).
