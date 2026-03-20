# PaperTrail

PaperTrail is a self-hosted AI research assistant for arXiv. You start with a research question, PaperTrail turns that into targeted arXiv searches, ranks the results, helps you ingest the best papers, and then guides the rest of the workflow: understanding, grounded Q&A, comparison, idea generation, and implementation planning.

This project is designed as a bounded research tool, not an autonomous web agent. It helps you search and reason over papers while keeping you in control of what gets ingested, compared, saved, and acted on.

> No accounts. No cloud. No Docker. Bring your own OpenAI API key and run everything locally.

## Product Vision

The intended finished PaperTrail experience looks like this:

1. Ask a research question in plain language.
2. PaperTrail generates a small set of targeted arXiv queries.
3. It searches arXiv, deduplicates results, and ranks papers with relevance scores and explanations.
4. You ingest the papers that matter, or skip discovery and add an arXiv link or PDF directly.
5. Each paper gets a structured breakdown: problem, method, contributions, results, limitations, and future work.
6. You ask grounded questions about a paper and get section-aware answers with citations back to the source text.
7. You compare multiple papers side by side across methods, datasets, strengths, weaknesses, and takeaways.
8. You generate follow-on research ideas by combining, extending, ablating, or applying what the papers describe.
9. You turn a paper into an implementation plan with algorithm steps, pseudocode, missing assumptions, and starter code.
10. Everything you care about stays in a local workspace: papers, discovery runs, saved comparisons, and saved ideas.

## Core Capabilities

- **Question-first discovery**: start from a research goal, not a paper URL.
- **arXiv-native search**: generate focused keyword queries, search arXiv, and rank the shortlist.
- **Direct paper ingestion**: add papers from an arXiv link or upload a PDF.
- **Structured understanding**: convert long papers into a consistent analysis you can scan quickly.
- **Grounded chat**: ask questions about a paper and get answers tied to specific sections.
- **Multi-paper comparison**: compare 2 to 5 papers in a structured matrix plus narrative summary.
- **Idea generation**: create concrete research directions from one paper or a small set of papers.
- **Paper-to-code support**: extract algorithms, identify missing details, and generate starter implementations.
- **Local workspace**: keep your research state on your machine with no hosted dependency.

## How It Is Intended to Feel

PaperTrail is meant to feel like a focused research workspace rather than a generic chatbot:

- The home screen centers on a research question and recent discovery runs.
- Discovery results show ranked paper cards, generated queries, relevance explanations, and one-click ingestion.
- Each paper page combines abstract, structured breakdown, full section view, grounded chat, and implementation tools.
- Comparison and idea-generation views are separate workflows, not buried in a single chat thread.
- A dashboard gives you one place to return to saved papers, comparisons, ideas, and prior discovery work.

## Boundaries

PaperTrail is intentionally constrained:

- It searches **arXiv only**.
- It does **not** browse the open web.
- It does **not** follow citation chains autonomously.
- It does **not** run open-ended multi-step research loops without approval.
- Search budgets are explicit and capped.
- The product is designed for **single-user, self-hosted** use.

The goal is trustworthy assistance, not autonomy theater.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4 |
| Backend | Python, FastAPI |
| Database | SQLite |
| Vector Store | ChromaDB |
| AI | OpenAI API |
| Discovery Source | arXiv API |

Everything runs locally. There is no external database, hosted backend, or required container setup.

## Requirements

- Python 3.11+
- Node.js 18+
- An [OpenAI API key](https://platform.openai.com)

## Quick Start

```bash
# Clone the repo
git clone https://github.com/andrewzagula/PaperTrail.git
cd PaperTrail

# Backend
pip install -r backend/requirements.txt

# Frontend
cd frontend
npm install
cd ..

# Configure environment
cp .env.example .env
# Set OPENAI_API_KEY in .env
```

Start the backend:

```bash
python run.py
```

Start the frontend in a second terminal:

```bash
cd frontend
npm run dev
```

Then open `http://localhost:3000`.

## Project Layout

```text
PaperTrail/
├── backend/          # FastAPI app, services, models, routers
├── frontend/         # Next.js app
├── data/             # Local runtime state (auto-created, gitignored)
├── run.py            # Backend entry point
└── .env.example      # Environment template
```

## Local Data Storage

PaperTrail stores its runtime state in `data/`:

| Path | Purpose |
|---|---|
| `data/papertrail.db` | SQLite database for papers, sections, chats, discovery runs, and saved items |
| `data/pdfs/` | Downloaded and uploaded PDFs |
| `data/chroma/` | ChromaDB vector embeddings for retrieval |

Delete `data/` if you want a full local reset.

## Operating Model

- Papers and sections are stored in SQLite for relational access.
- Section embeddings are stored in ChromaDB for retrieval.
- Discovery uses the arXiv API plus LLM-generated queries and ranking.
- Grounded chat retrieves only from the selected paper's sections.
- All saved research artifacts remain local to your machine.

## Troubleshooting

**Backend will not start**  
Install backend dependencies and make sure `OPENAI_API_KEY` is set in `.env`.

**Frontend cannot reach the backend**  
The backend should be running on `http://localhost:8000`. If you changed ports, update the frontend API configuration and CORS settings.

**Embeddings fail but papers still save**  
This is expected behavior. PaperTrail is designed to preserve the paper even if embedding generation fails.

**Discovery quality is poor**  
arXiv search is keyword-based. More specific technical phrasing usually produces better results.

## License

[MIT](LICENSE)
