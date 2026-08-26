# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Anyone reading technical papers: researchers, engineers, and students working through an
arXiv-shaped literature. Not scoped to ML/AI, though the arXiv-first ingest path and the
recommended sample papers mean that is the best-served case today.

The user runs PaperTrail themselves on their own machine. They are alone in the app: there
is one local user record, no accounts, no invitations, no shared workspace. Their situation
is a reading session, not an administrative one - they arrive with a question or a PDF and
want to get to understanding.

## Product Purpose

PaperTrail is a self-hosted research workspace that carries a paper through a full arc:
discover from a plain-language research question, ingest into a local library, read as a
structured breakdown, ask grounded questions of the text, compare against other saved
papers, generate follow-on research ideas, and produce an implementation-oriented plan.

Success is that the user goes from "I have a question" to "I understand this literature and
have something to build" without leaving the app and without their library living on
someone else's server.

## Positioning

The full chain lives in one local workspace. Tools that stop at discovery, or at chat over a
PDF, cannot follow a paper through comparison and into an implementation plan; hosted tools
that do cover the chain require handing over the library. PaperTrail keeps state on the
user's disk - SQLite, local PDF files, a local ChromaDB vector store - and lets the user
choose which model provider, if any, sees their text. Ollama plus local sentence-transformers
is a genuinely fully-local path.

## Operating Context

- Two processes on localhost: FastAPI backend on `:8000`, Next.js frontend on `:3000`.
  Configuration is a `.env` file in the repo root, edited by hand.
- Existing routes: `/` (discover), `/discover/[id]` (a run), `/papers/[id]` (breakdown, chat,
  sections, implement), `/papers/new` (ingest), `/compare`, `/ideas`, `/dashboard`,
  `/dashboard/saved/[id]`.
- Work is long-running and failable by nature. Discovery runs take minutes, span multiple
  generated queries, and can partially fail; ingestion depends on the public arXiv API and on
  PDFs having extractable text; embeddings can be `ready`, `stale`, `missing`, or `failed`
  against the active backend. Progress, partial results, and failure states are ordinary
  operating conditions, not edge cases.
- Setup is a real part of the experience. `/health/details` reports provider and model names,
  local data paths, missing settings, and placeholder values; `?probe=true` spends a few
  tokens to verify credentials actually work.

## Capabilities and Constraints

- Discover and relevance-rank arXiv papers from a research question, with the generated
  queries and the ranking rationale exposed to the user.
- Ingest from arXiv or an uploaded PDF; parse with PyMuPDF; split into sections; embed into
  a ChromaDB collection namespaced by embedding provider and model.
- Structured paper breakdowns and retrieval-grounded chat over the paper's own text.
- Comparison across saved papers on normalized dimensions, plus a narrative synthesis.
- Idea generation with critique, and implementation plans with pseudocode, setup notes,
  tests, and starter code.
- Provider abstraction over OpenAI, Anthropic, Gemini, OpenAI-compatible endpoints, and
  Ollama; embeddings via OpenAI or local sentence-transformers. Per-workflow model overrides
  exist for eleven distinct steps.
- Stack is fixed by the existing codebase: Next.js 16 / React 19 / TypeScript / Tailwind v4
  on the front, FastAPI / SQLAlchemy / SQLite / ChromaDB on the back. The frontend currently
  has no component library and no animation library installed.
- No authentication layer. The backend is not hardened for untrusted networks.
- MIT licensed, public repository, no telemetry.

### Open decisions

- **Visual world: undecided.** An "Instrument" direction exists as a published artifact
  (indigo/periwinkle accent, Instrument Sans with Geist Mono for counts and statuses, dark
  default with a matching light theme, command palette). The user has explicitly *not* made
  it binding - it is one option among others, and a later visual-world pass owns the choice.
  Nothing in this file should be read as approving it.
- Whether existing routes and information architecture are fixed was left open. Treat them as
  the current shape, not as a preservation contract.
- Whether provider-agnosticism is a surface-level commitment was left open. It is true of the
  code today; it is not recorded here as a design constraint.

## Brand Commitments

The name is PaperTrail. No logo, wordmark, palette, or type commitment exists.

## Evidence on Hand

- Real, working product: the whole pipeline runs locally. Screens can show true output rather
  than invented output.
- `README.md` carries accurate setup, configuration, troubleshooting, and privacy language.
- Real sample papers named in the README: arXiv `1706.03762` and `1409.0473`.
- **Absent, and must not be fabricated:** users, testimonials, install counts, GitHub stars,
  benchmarks, accuracy numbers, evaluation results, pricing, hosted offering, company,
  team, press, or roadmap commitments. There is no deployment target beyond localhost.

## Product Principles

1. **The user's library stays on the user's machine.** Every feature must remain honest about
   what leaves the machine and when. Local-first is the product, not a deployment mode.
2. **One person, alone, on localhost.** No accounts, no auth screens, no sharing, no
   collaboration affordances, no seats. Anything that implies other people is wrong.
3. **Generated output is scaffolding, and says so.** Breakdowns, rankings, comparisons, ideas,
   and implementation code are model output over paper text. They carry their provenance and
   their limits; they never present themselves as verified fact or exhaustive review.
4. **Show the work.** Generated queries, relevance reasoning, section citations, coverage
   gaps, and embedding state are surfaced rather than hidden. The user is a researcher and is
   expected to judge the pipeline, not trust it.
5. **Long, failable work is the normal case.** Progress, partial results, retry, and precise
   failure reporting are first-class, not error handling bolted onto a happy path.

## Accessibility & Inclusion

No product-specific standard has been established beyond ordinary web accessibility
expectations (WCAG AA contrast, keyboard operability, honored `prefers-reduced-motion`).
