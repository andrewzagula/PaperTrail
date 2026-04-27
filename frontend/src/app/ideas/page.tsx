"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_IDEA_SELECTION = 5;

interface PaperListItem {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
  has_structured_breakdown?: boolean;
}

interface SelectedIdeaPaperResponse {
  id: string;
  title: string;
  authors: string | null;
  arxiv_url: string | null;
  created_at: string;
}

type TransformationType = "combine" | "ablate" | "extend" | "apply";
type Feasibility = "low" | "medium" | "high";

interface IdeaResponse {
  title: string;
  transformation_type: TransformationType;
  description: string;
  why_interesting: string;
  feasibility: Feasibility;
  evidence_basis: string[];
  risks_or_unknowns: string[];
  warnings: string[];
}

interface IdeaGenerationResponse {
  selected_papers: SelectedIdeaPaperResponse[];
  source_topic: string | null;
  ideas: IdeaResponse[];
  warnings: string[];
}

interface SaveIdeasResponse {
  id: string;
  title: string;
  item_type: "idea";
  paper_ids: string[];
  created_at: string;
}

const TRANSFORMATION_LABELS: Record<TransformationType, string> = {
  combine: "Combine",
  ablate: "Ablate",
  extend: "Extend",
  apply: "Apply",
};

const FEASIBILITY_STYLES: Record<Feasibility, string> = {
  low: "border-red-500/20 bg-red-500/10 text-red-500",
  medium: "border-amber-500/20 bg-amber-500/10 text-amber-600",
  high: "border-[var(--primary)]/20 bg-[var(--primary)]/10 text-[var(--primary)]",
};

function formatDate(value: string): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return "Unknown date";
  }

  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function normalizeQueryPaperIds(values: string[]): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();

  for (const value of values) {
    const id = value.trim();
    if (!id || seen.has(id)) {
      continue;
    }

    seen.add(id);
    ids.push(id);
    if (ids.length >= MAX_IDEA_SELECTION) {
      break;
    }
  }

  return ids;
}

function createSourceSignature(paperIds: string[], topic: string): string {
  return `${paperIds.join(",")}::${topic.trim()}`;
}

function createSaveKey(result: IdeaGenerationResponse, title: string): string {
  const paperIds = result.selected_papers.map((paper) => paper.id).join(",");
  return `${paperIds}::${result.source_topic || ""}::${title}`;
}

function createDefaultIdeasTitle(result: IdeaGenerationResponse): string {
  const topic = result.source_topic?.trim();
  const [firstPaper, ...remainingPapers] = result.selected_papers;

  if (!firstPaper && topic) {
    return `Ideas: ${topic}`;
  }

  if (!firstPaper) {
    return "Ideas";
  }

  if (remainingPapers.length === 0) {
    return `Ideas: ${firstPaper.title}`;
  }

  return `Ideas: ${firstPaper.title} (+${remainingPapers.length} more)`;
}

function IdeasPageContent() {
  const searchParams = useSearchParams();

  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(true);
  const [libraryError, setLibraryError] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectionMessage, setSelectionMessage] = useState("");
  const [topic, setTopic] = useState("");
  const [ideaResult, setIdeaResult] = useState<IdeaGenerationResponse | null>(null);
  const [resultSourceSignature, setResultSourceSignature] = useState("");
  const [generationLoading, setGenerationLoading] = useState(false);
  const [generationError, setGenerationError] = useState("");
  const [saveTitle, setSaveTitle] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState("");
  const [lastSavedKey, setLastSavedKey] = useState("");

  useEffect(() => {
    const queryPaperIds = searchParams.getAll("paper");
    const normalizedIds = normalizeQueryPaperIds(queryPaperIds);
    setSelectedIds(normalizedIds);

    if (queryPaperIds.length > MAX_IDEA_SELECTION) {
      setSelectionMessage(`Using the first ${MAX_IDEA_SELECTION} papers from the link.`);
    }
  }, [searchParams]);

  useEffect(() => {
    async function loadPapers() {
      setLibraryLoading(true);
      setLibraryError("");

      try {
        const res = await fetch(`${API_URL}/papers/`);
        if (!res.ok) {
          throw new Error("Failed to load your paper library.");
        }

        const data: PaperListItem[] = await res.json();
        setPapers(data);
      } catch (err) {
        setLibraryError(
          err instanceof Error ? err.message : "Failed to load your paper library.",
        );
      } finally {
        setLibraryLoading(false);
      }
    }

    loadPapers();
  }, []);

  useEffect(() => {
    if (libraryLoading) {
      return;
    }

    const availableIds = new Set(papers.map((paper) => paper.id));
    setSelectedIds((current) => current.filter((paperId) => availableIds.has(paperId)));
  }, [libraryLoading, papers]);

  const selectedPapers = useMemo(
    () =>
      selectedIds
        .map((paperId) => papers.find((paper) => paper.id === paperId))
        .filter((paper): paper is PaperListItem => Boolean(paper)),
    [papers, selectedIds],
  );

  const sourceSignature = createSourceSignature(selectedIds, topic);
  const hasSource = selectedIds.length > 0 || topic.trim().length > 0;
  const generationDisabled =
    generationLoading || !hasSource || (libraryLoading && selectedIds.length > 0);

  const clearGeneratedOutput = () => {
    setIdeaResult(null);
    setResultSourceSignature("");
    setGenerationError("");
    setSaveTitle("");
    setSaveLoading(false);
    setSaveError("");
    setSaveSuccess("");
    setLastSavedKey("");
  };

  const handleTopicChange = (value: string) => {
    setTopic(value);
    if (ideaResult || generationError || saveSuccess || saveError) {
      clearGeneratedOutput();
    }
  };

  const handleTogglePaper = (paperId: string) => {
    if (selectedIds.includes(paperId)) {
      setSelectedIds(selectedIds.filter((id) => id !== paperId));
      setSelectionMessage("");
      clearGeneratedOutput();
      return;
    }

    if (selectedIds.length >= MAX_IDEA_SELECTION) {
      setSelectionMessage(`You can use up to ${MAX_IDEA_SELECTION} papers for ideas.`);
      return;
    }

    setSelectedIds([...selectedIds, paperId]);
    setSelectionMessage("");
    clearGeneratedOutput();
  };

  const handleGenerateIdeas = async () => {
    const normalizedTopic = topic.trim();

    setGenerationError("");
    setSelectionMessage("");

    if (!selectedIds.length && !normalizedTopic) {
      setGenerationError("Select at least one paper or enter a topic.");
      return;
    }

    setGenerationLoading(true);
    setSaveError("");
    setSaveSuccess("");

    try {
      const body: { paper_ids?: string[]; topic?: string } = {};
      if (selectedIds.length > 0) {
        body.paper_ids = selectedIds;
      }
      if (normalizedTopic) {
        body.topic = normalizedTopic;
      }

      const res = await fetch(`${API_URL}/papers/ideas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Idea generation failed.");
      }

      const data: IdeaGenerationResponse = await res.json();
      setIdeaResult(data);
      setResultSourceSignature(sourceSignature);
      setSaveTitle(createDefaultIdeasTitle(data));
      setSaveError("");
      setSaveSuccess("");
      setLastSavedKey("");
    } catch (err) {
      setIdeaResult(null);
      setResultSourceSignature("");
      setGenerationError(
        err instanceof Error ? err.message : "Idea generation failed.",
      );
    } finally {
      setGenerationLoading(false);
    }
  };

  const handleSaveIdeas = async () => {
    if (!ideaResult) {
      return;
    }

    const normalizedTitle = saveTitle.trim();
    if (!normalizedTitle) {
      setSaveError("Idea title is required.");
      setSaveSuccess("");
      return;
    }

    const saveKey = createSaveKey(ideaResult, normalizedTitle);
    if (saveKey === lastSavedKey) {
      setSaveError("This idea result is already saved with that title.");
      setSaveSuccess("");
      return;
    }

    setSaveLoading(true);
    setSaveError("");
    setSaveSuccess("");

    try {
      const paperIds = ideaResult.selected_papers.map((paper) => paper.id);
      const res = await fetch(`${API_URL}/papers/ideas/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: normalizedTitle,
          paper_ids: paperIds,
          idea_result: ideaResult,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to save ideas.");
      }

      const data: SaveIdeasResponse = await res.json();
      setSaveTitle(data.title);
      setSaveSuccess(`Saved ideas as "${data.title}".`);
      setLastSavedKey(saveKey);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save ideas.");
    } finally {
      setSaveLoading(false);
    }
  };

  const resultIsStale =
    Boolean(ideaResult) && resultSourceSignature !== sourceSignature;

  return (
    <div className="min-h-screen px-6 py-10">
      <main className="mx-auto max-w-7xl space-y-8">
        <div className="flex flex-col gap-4 border-b border-[var(--border)] pb-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <a
              href="/"
              className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
            >
              &larr; Home
            </a>
            <div>
              <h1 className="text-4xl font-bold tracking-tight">Generate Ideas</h1>
              <p className="mt-2 max-w-3xl text-[var(--muted)] leading-relaxed">
                Choose paper sources, add an optional focus, and generate bounded
                research ideas with evidence and uncertainty surfaced.
              </p>
            </div>
          </div>

          <div className="rounded-full border border-[var(--border)] bg-[var(--card)] px-4 py-2 text-sm text-[var(--muted)]">
            {selectedIds.length} / {MAX_IDEA_SELECTION} papers selected
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
          <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold">Sources</h2>
                <span className="text-xs uppercase tracking-wide text-[var(--muted)]">
                  manual run
                </span>
              </div>

              <label
                htmlFor="idea-topic"
                className="mt-5 block text-sm font-medium text-[var(--foreground)]"
              >
                Topic or focus
              </label>
              <textarea
                id="idea-topic"
                value={topic}
                onChange={(event) => handleTopicChange(event.target.value)}
                placeholder="Optional focus, research question, domain, or evaluation angle"
                disabled={generationLoading}
                rows={4}
                className="mt-2 w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-sm leading-6 outline-none transition-colors placeholder:text-[var(--muted)] focus:border-[var(--primary)] disabled:opacity-60"
              />

              <div className="mt-5">
                <div className="flex items-center justify-between gap-4">
                  <h3 className="text-sm font-semibold">Selected Papers</h3>
                  {selectedPapers.length > 0 && (
                    <button
                      onClick={() => {
                        setSelectedIds([]);
                        setSelectionMessage("");
                        clearGeneratedOutput();
                      }}
                      disabled={generationLoading}
                      className="text-xs text-[var(--muted)] transition-colors hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Clear
                    </button>
                  )}
                </div>

                {selectedPapers.length === 0 ? (
                  <div className="mt-3 rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-sm text-[var(--muted)]">
                    No papers selected.
                  </div>
                ) : (
                  <div className="mt-3 space-y-3">
                    {selectedPapers.map((paper) => (
                      <div
                        key={paper.id}
                        className="rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h4 className="font-medium line-clamp-2">{paper.title}</h4>
                            {paper.authors && (
                              <p className="mt-1 text-sm text-[var(--muted)] line-clamp-2">
                                {paper.authors}
                              </p>
                            )}
                          </div>
                          <button
                            onClick={() => handleTogglePaper(paper.id)}
                            disabled={generationLoading}
                            className="shrink-0 text-xs text-[var(--muted)] transition-colors hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {selectionMessage && (
                <div className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-sm">
                  {selectionMessage}
                </div>
              )}

              {generationError && (
                <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
                  {generationError}
                </div>
              )}

              <button
                onClick={handleGenerateIdeas}
                disabled={generationDisabled}
                className="mt-5 w-full rounded-xl bg-[var(--primary)] px-4 py-3 font-medium text-white transition-colors hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {generationLoading ? "Generating..." : "Generate Ideas"}
              </button>
            </section>
          </aside>

          <section className="space-y-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold">Paper Library</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Select up to five library papers as evidence sources.
                </p>
              </div>

              <a
                href="/papers/new"
                className="text-sm text-[var(--primary)] hover:underline"
              >
                Add another paper
              </a>
            </div>

            {libraryLoading ? (
              <div className="flex min-h-64 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--card)]">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
              </div>
            ) : libraryError ? (
              <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
                {libraryError}
              </div>
            ) : papers.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--card)] px-6 py-12 text-center">
                <h3 className="text-lg font-semibold">Your library is empty</h3>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Topic-only idea generation is still available.
                </p>
                <a
                  href="/papers/new"
                  className="mt-4 inline-flex rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--foreground)] transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)]"
                >
                  Upload a paper
                </a>
              </div>
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                {papers.map((paper) => {
                  const isSelected = selectedIds.includes(paper.id);
                  const selectionLocked =
                    !isSelected && selectedIds.length >= MAX_IDEA_SELECTION;

                  return (
                    <button
                      key={paper.id}
                      onClick={() => handleTogglePaper(paper.id)}
                      disabled={selectionLocked || generationLoading}
                      aria-pressed={isSelected}
                      className={`rounded-2xl border p-5 text-left transition-all ${
                        isSelected
                          ? "border-[var(--primary)] bg-[var(--primary)]/5"
                          : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--primary)]/30"
                      } ${
                        selectionLocked || generationLoading
                          ? "cursor-not-allowed opacity-60"
                          : ""
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <h3 className="text-lg font-semibold line-clamp-2">
                            {paper.title}
                          </h3>
                          {paper.authors && (
                            <p className="mt-1 text-sm text-[var(--muted)] line-clamp-2">
                              {paper.authors}
                            </p>
                          )}
                        </div>

                        <span
                          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
                            isSelected
                              ? "bg-[var(--primary)] text-white"
                              : "border border-[var(--border)] text-[var(--muted)]"
                          }`}
                        >
                          {isSelected
                            ? "Selected"
                            : selectionLocked
                              ? "Limit reached"
                              : "Select"}
                        </span>
                      </div>

                      {paper.abstract && (
                        <p className="mt-3 text-sm leading-relaxed text-[var(--muted)] line-clamp-4">
                          {paper.abstract}
                        </p>
                      )}

                      <div className="mt-4 flex flex-wrap gap-2">
                        {typeof paper.has_structured_breakdown === "boolean" && (
                          <span
                            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                              paper.has_structured_breakdown
                                ? "bg-[var(--primary)]/10 text-[var(--primary)]"
                                : "border border-[var(--border)] text-[var(--muted)]"
                            }`}
                          >
                            {paper.has_structured_breakdown
                              ? "Structured data ready"
                              : "May need processing"}
                          </span>
                        )}
                        <span className="rounded-full border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--muted)]">
                          Added {formatDate(paper.created_at)}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}

            {resultIsStale && (
              <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-600">
                Sources changed. Run idea generation again for the current setup.
              </div>
            )}

            {ideaResult && !resultIsStale && (
              <section className="space-y-6 border-t border-[var(--border)] pt-8">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                  <div>
                    <h2 className="text-2xl font-semibold">Generated Ideas</h2>
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      {ideaResult.ideas.length} ideas generated from the selected sources.
                    </p>
                  </div>

                  <div className="flex flex-col gap-3 xl:items-end">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                      <input
                        type="text"
                        value={saveTitle}
                        maxLength={1000}
                        disabled={saveLoading}
                        onChange={(event) => {
                          setSaveTitle(event.target.value);
                          setSaveError("");
                          setSaveSuccess("");
                        }}
                        placeholder="Idea result title"
                        className="w-full min-w-0 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm outline-none transition-colors focus:border-[var(--primary)] sm:min-w-96"
                      />
                      <button
                        onClick={handleSaveIdeas}
                        disabled={saveLoading}
                        className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm font-medium transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {saveLoading ? "Saving..." : "Save Ideas"}
                      </button>
                    </div>
                    {saveError && <p className="text-sm text-red-500">{saveError}</p>}
                    {saveSuccess && (
                      <p className="text-sm text-[var(--primary)]">{saveSuccess}</p>
                    )}
                  </div>
                </div>

                <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
                  <h3 className="text-lg font-semibold">Source Basis</h3>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {ideaResult.selected_papers.map((paper) => (
                      <a
                        key={paper.id}
                        href={`/papers/${paper.id}`}
                        className="max-w-full rounded-full border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--foreground)] transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)]"
                      >
                        <span className="line-clamp-1">{paper.title}</span>
                      </a>
                    ))}
                    {ideaResult.source_topic && (
                      <span className="max-w-full rounded-full bg-[var(--primary)]/10 px-3 py-1.5 text-sm text-[var(--primary)]">
                        <span className="line-clamp-1">{ideaResult.source_topic}</span>
                      </span>
                    )}
                    {ideaResult.selected_papers.length === 0 &&
                      !ideaResult.source_topic && (
                        <span className="text-sm text-[var(--muted)]">
                          No source basis returned.
                        </span>
                      )}
                  </div>
                </div>

                {ideaResult.warnings.length > 0 && (
                  <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
                    <h3 className="text-lg font-semibold">Warnings</h3>
                    <ul className="mt-4 space-y-3 text-sm text-[var(--muted)]">
                      {ideaResult.warnings.map((warning) => (
                        <li
                          key={warning}
                          className="rounded-xl bg-[var(--background)] px-4 py-3 leading-relaxed"
                        >
                          {warning}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="grid gap-5 lg:grid-cols-2">
                  {ideaResult.ideas.map((idea, index) => (
                    <article
                      key={`${idea.title}-${index}`}
                      className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5"
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap gap-2">
                            <span className="rounded-full bg-[var(--primary)]/10 px-2.5 py-1 text-xs font-medium text-[var(--primary)]">
                              {TRANSFORMATION_LABELS[idea.transformation_type]}
                            </span>
                            <span
                              className={`rounded-full border px-2.5 py-1 text-xs font-medium ${FEASIBILITY_STYLES[idea.feasibility]}`}
                            >
                              {idea.feasibility} feasibility
                            </span>
                          </div>
                          <h3 className="mt-3 text-xl font-semibold leading-snug">
                            {idea.title}
                          </h3>
                        </div>
                      </div>

                      <div className="mt-4 space-y-4 text-sm leading-6">
                        <div>
                          <h4 className="font-semibold text-[var(--foreground)]">
                            Description
                          </h4>
                          <p className="mt-1 text-[var(--foreground)]/90">
                            {idea.description}
                          </p>
                        </div>

                        <div>
                          <h4 className="font-semibold text-[var(--foreground)]">
                            Why Interesting
                          </h4>
                          <p className="mt-1 text-[var(--foreground)]/90">
                            {idea.why_interesting}
                          </p>
                        </div>

                        <div>
                          <h4 className="font-semibold text-[var(--foreground)]">
                            Evidence Basis
                          </h4>
                          <ul className="mt-2 space-y-2">
                            {idea.evidence_basis.map((evidence) => (
                              <li
                                key={evidence}
                                className="rounded-lg bg-[var(--background)] px-3 py-2 text-[var(--muted)]"
                              >
                                {evidence}
                              </li>
                            ))}
                          </ul>
                        </div>

                        <div>
                          <h4 className="font-semibold text-[var(--foreground)]">
                            Risks or Unknowns
                          </h4>
                          <ul className="mt-2 space-y-2">
                            {idea.risks_or_unknowns.map((risk) => (
                              <li
                                key={risk}
                                className="rounded-lg bg-[var(--background)] px-3 py-2 text-[var(--muted)]"
                              >
                                {risk}
                              </li>
                            ))}
                          </ul>
                        </div>

                        {idea.warnings.length > 0 && (
                          <div>
                            <h4 className="font-semibold text-[var(--foreground)]">
                              Warnings
                            </h4>
                            <ul className="mt-2 space-y-2">
                              {idea.warnings.map((warning) => (
                                <li
                                  key={warning}
                                  className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-amber-600"
                                >
                                  {warning}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

export default function IdeasPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
        </div>
      }
    >
      <IdeasPageContent />
    </Suspense>
  );
}
