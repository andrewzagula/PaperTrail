# Papertrail

An AI research copilot that helps you go from paper to understanding to comparison to idea to implementation.

Unlike generic "chat with PDF" tools, Papertrail provides **structured breakdowns**, **cross-paper comparison**, **research idea generation**, and **code implementation** from academic papers.

## Features

- **Upload papers** — paste an arXiv link or upload a PDF
- **Structured breakdown** — get a clear analysis: Problem, Method, Key Contributions, Results, Limitations, Future Work *(coming soon)*
- **Section-aware Q&A** — ask grounded questions with citations back to specific sections *(coming soon)*
- **Multi-paper compare** — select 2-5 papers and get a structured comparison table *(coming soon)*
- **Idea generation** — generate novel research ideas using structured transformations *(coming soon)*
- **Paper to code** — turn methods into pseudocode and Python/PyTorch starter code *(coming soon)*

## Requirements

- **Python 3.11+**
- **Node.js 18+**
- **OpenAI API key** — get one at [platform.openai.com](https://platform.openai.com)

## Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/papertrail.git
cd papertrail

# Install backend dependencies
pip install -r backend/requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Configure your API key
cp .env.example .env
# Edit .env and add your OpenAI API key
```

## Running

You need two terminal windows:

**Terminal 1 — Backend:**
```bash
python run.py
# API running at http://localhost:8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
# App running at http://localhost:3000
```

Open **http://localhost:3000** in your browser.

## How It Works

1. Paste an arXiv URL or upload a PDF
2. Papertrail extracts the text, detects sections, and generates embeddings
3. You get a structured view of the paper with navigable sections
4. *(Coming soon)* Ask questions, compare papers, generate ideas, and get starter code

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS v4 |
| Backend | Python, FastAPI |
| Database | SQLite (zero config) |
| Vector Store | ChromaDB (embedded) |
| AI | OpenAI API |

No Docker required. No external database to set up. Everything runs locally.

## Data Storage

All your data lives in the `data/` directory (auto-created on first run):
- `data/papertrail.db` — SQLite database (papers, sections, chats)
- `data/pdfs/` — downloaded/uploaded PDF files
- `data/chroma/` — vector embeddings for search

To reset everything, delete the `data/` directory.

## Project Status

This is an active MVP build. See [PROGRESS.md](PROGRESS.md) for detailed phase tracking.

| Phase | Status |
|---|---|
| Paper Ingestion | Done |
| Structured Breakdown | Next |
| Section-Aware Chat | Planned |
| Multi-Paper Compare | Planned |
| Idea Generation | Planned |
| Paper to Code | Planned |

## Contributing

Contributions welcome. Read [CLAUDE.md](CLAUDE.md) for architecture details, coding patterns, and conventions.

## License

MIT
