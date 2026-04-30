"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  MAX_COMPARE_SELECTION,
  getStoredCompareSelection,
  mergeCompareSelection,
  setStoredCompareSelection,
} from "@/lib/compare-selection";
import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PaperListItem {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
  has_structured_breakdown: boolean;
}

interface SelectedPaperResponse {
  id: string;
  title: string;
  authors: string | null;
  arxiv_url: string | null;
  created_at: string;
}

interface NormalizedProfile {
  paper_id: string;
  title: string;
  authors: string;
  problem: string;
  method: string;
  dataset_or_eval_setup: string;
  key_results: string;
  strengths: string;
  weaknesses: string;
  evidence_notes: Record<string, string[]>;
  warnings: string[];
}

interface ComparisonTableColumn {
  key: string;
  label: string;
}

interface ComparisonTableRow {
  key: string;
  label: string;
  values: string[];
}

interface CompareResponse {
  selected_papers: SelectedPaperResponse[];
  normalized_profiles: NormalizedProfile[];
  comparison_table: {
    columns: ComparisonTableColumn[];
    rows: ComparisonTableRow[];
  };
  narrative_summary: string;
  warnings: string[];
}

interface SaveComparisonResponse {
  id: string;
  title: string;
  item_type: "comparison";
  paper_ids: string[];
  created_at: string;
}

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

function buildCompareResultSignature(result: CompareResponse): string {
  return result.selected_papers.map((paper) => paper.id).join(",");
}

function createDefaultComparisonTitle(result: CompareResponse): string {
  const [firstPaper, secondPaper, ...remainingPapers] = result.selected_papers;
  if (!firstPaper || !secondPaper) {
    return "Comparison";
  }

  if (remainingPapers.length === 0) {
    return `Comparison: ${firstPaper.title} vs ${secondPaper.title}`;
  }

  return `Comparison: ${firstPaper.title} vs ${secondPaper.title} (+${remainingPapers.length} more)`;
}

function ComparePageContent() {
  const searchParams = useSearchParams();

  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(true);
  const [libraryError, setLibraryError] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectionMessage, setSelectionMessage] = useState("");
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState("");
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null);
  const [lastComparedSignature, setLastComparedSignature] = useState("");
  const [saveTitle, setSaveTitle] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState("");
  const [lastSavedKey, setLastSavedKey] = useState("");

  useEffect(() => {
    setSelectedIds(
      mergeCompareSelection(
        searchParams.getAll("paper"),
        getStoredCompareSelection(),
      ),
    );
  }, [searchParams]);

  useEffect(() => {
    setStoredCompareSelection(selectedIds);
  }, [selectedIds]);

  useEffect(() => {
    async function loadPapers() {
      setLibraryLoading(true);
      setLibraryError("");

      try {
        const res = await fetch(`${API_URL}/papers/`);
        if (!res.ok) {
          throw new Error(
            await getApiErrorMessage(res, "Failed to load your paper library."),
          );
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

  useEffect(() => {
    if (selectedIds.join(",") !== lastComparedSignature) {
      setCompareResult(null);
      setCompareError("");
    }
  }, [lastComparedSignature, selectedIds]);

  useEffect(() => {
    if (!compareResult) {
      setSaveTitle("");
      setSaveLoading(false);
      setSaveError("");
      setSaveSuccess("");
      setLastSavedKey("");
      return;
    }

    setSaveTitle(createDefaultComparisonTitle(compareResult));
    setSaveLoading(false);
    setSaveError("");
    setSaveSuccess("");
    setLastSavedKey("");
  }, [compareResult]);

  const selectedPapers = selectedIds
    .map((paperId) => papers.find((paper) => paper.id === paperId))
    .filter((paper): paper is PaperListItem => Boolean(paper));

  const selectedPapersNeedingProcessing = selectedPapers.filter(
    (paper) => !paper.has_structured_breakdown,
  );
  const compareResultSignature = compareResult
    ? buildCompareResultSignature(compareResult)
    : "";

  const profileById: Record<string, NormalizedProfile> = {};
  if (compareResult) {
    for (const profile of compareResult.normalized_profiles) {
      profileById[profile.paper_id] = profile;
    }
  }

  const handleTogglePaper = (paperId: string) => {
    if (compareLoading) {
      return;
    }

    let nextMessage = "";

    setSelectedIds((current) => {
      if (current.includes(paperId)) {
        return current.filter((id) => id !== paperId);
      }

      if (current.length >= MAX_COMPARE_SELECTION) {
        nextMessage = `You can compare up to ${MAX_COMPARE_SELECTION} papers at a time.`;
        return current;
      }

      return [...current, paperId];
    });

    setSelectionMessage(nextMessage);
  };

  const handleCompare = async () => {
    if (compareLoading) {
      return;
    }

    setCompareError("");
    setSelectionMessage("");

    if (selectedIds.length < 2) {
      setCompareError("Select at least 2 papers to compare.");
      return;
    }

    setCompareLoading(true);

    try {
      const res = await fetch(`${API_URL}/papers/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: selectedIds }),
      });

      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Comparison failed."));
      }

      const data: CompareResponse = await res.json();
      setCompareResult(data);
      setLastComparedSignature(selectedIds.join(","));
    } catch (err) {
      setCompareError(err instanceof Error ? err.message : "Comparison failed.");
    } finally {
      setCompareLoading(false);
    }
  };

  const handleSaveComparison = async () => {
    if (!compareResult) {
      return;
    }

    const normalizedTitle = saveTitle.trim();
    if (!normalizedTitle) {
      setSaveError("Comparison title is required.");
      setSaveSuccess("");
      return;
    }

    const saveKey = `${compareResultSignature}::${normalizedTitle}`;
    if (saveKey === lastSavedKey) {
      setSaveError("This comparison is already saved with that title.");
      setSaveSuccess("");
      return;
    }

    setSaveLoading(true);
    setSaveError("");
    setSaveSuccess("");

    try {
      const res = await fetch(`${API_URL}/papers/compare/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: normalizedTitle,
          paper_ids: compareResult.selected_papers.map((paper) => paper.id),
          comparison: compareResult,
        }),
      });

      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to save comparison."),
        );
      }

      const data: SaveComparisonResponse = await res.json();
      setSaveTitle(data.title);
      setSaveSuccess(`Saved comparison as "${data.title}".`);
      setLastSavedKey(saveKey);
    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to save comparison.",
      );
    } finally {
      setSaveLoading(false);
    }
  };

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
              <h1 className="text-4xl font-bold tracking-tight">Compare Papers</h1>
              <p className="mt-2 max-w-3xl text-[var(--muted)] leading-relaxed">
                Choose 2 to 5 papers from your library, then run a bounded
                compare pass for a narrative summary, side-by-side matrix, and
                missing-data warnings.
              </p>
            </div>
          </div>

          <div className="rounded-full border border-[var(--border)] bg-[var(--card)] px-4 py-2 text-sm text-[var(--muted)]">
            {selectedIds.length} / {MAX_COMPARE_SELECTION} selected
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
          <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold">Selection</h2>
                <span className="text-xs uppercase tracking-wide text-[var(--muted)]">
                  manual run only
                </span>
              </div>

              <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
                The compare workflow never auto-runs on page load. Adjust the
                selection first, then trigger it when you are ready.
              </p>

              {selectedPapers.length === 0 ? (
                <div className="mt-4 rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-sm text-[var(--muted)]">
                  No papers selected yet. Pick papers from the library to build
                  a compare set.
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  {selectedPapers.map((paper) => (
                    <div
                      key={paper.id}
                      className="rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="font-medium line-clamp-2">{paper.title}</h3>
                          {paper.authors && (
                            <p className="mt-1 text-sm text-[var(--muted)] line-clamp-2">
                              {paper.authors}
                            </p>
                          )}
                        </div>

                        <button
                          onClick={() => handleTogglePaper(paper.id)}
                          disabled={compareLoading}
                          className="shrink-0 text-xs text-[var(--muted)] hover:text-red-500 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Remove
                        </button>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                            paper.has_structured_breakdown
                              ? "bg-[var(--primary)]/10 text-[var(--primary)]"
                              : "border border-[var(--border)] text-[var(--muted)]"
                          }`}
                        >
                          {paper.has_structured_breakdown
                            ? "Structured data ready"
                            : "Needs extra processing"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {selectedPapersNeedingProcessing.length > 0 && (
                <div className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-sm leading-relaxed">
                  <p className="font-medium">Extra processing expected</p>
                  <p className="mt-1 text-[var(--muted)]">
                    {selectedPapersNeedingProcessing
                      .map((paper) => paper.title)
                      .join(", ")}{" "}
                    {selectedPapersNeedingProcessing.length === 1 ? "does" : "do"} not
                    have a stored structured breakdown yet. The backend will
                    generate missing breakdowns during compare.
                  </p>
                </div>
              )}

              {selectionMessage && (
                <div className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-sm">
                  {selectionMessage}
                </div>
              )}

              {compareError && (
                <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
                  {compareError}
                </div>
              )}

              <button
                onClick={handleCompare}
                disabled={compareLoading || selectedIds.length < 2}
                className="mt-5 w-full rounded-xl bg-[var(--primary)] px-4 py-3 font-medium text-white transition-colors hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {compareLoading
                  ? "Comparing..."
                  : `Compare ${Math.max(selectedIds.length, 2)} Papers`}
              </button>
            </section>
          </aside>

          <section className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold">Paper Library</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Toggle papers into the compare set. The selection persists
                  across pages so you can queue papers from the library or from
                  an individual paper view.
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
                  Upload or ingest papers first, then come back here to compare
                  them.
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
                    !isSelected && selectedIds.length >= MAX_COMPARE_SELECTION;

                  return (
                    <button
                      key={paper.id}
                      onClick={() => handleTogglePaper(paper.id)}
                      disabled={selectionLocked || compareLoading}
                      aria-pressed={isSelected}
                      className={`rounded-2xl border p-5 text-left transition-all ${
                        isSelected
                          ? "border-[var(--primary)] bg-[var(--primary)]/5"
                          : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--primary)]/30"
                      } ${
                        selectionLocked || compareLoading
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
                            : compareLoading
                              ? "Locked"
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
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                            paper.has_structured_breakdown
                              ? "bg-[var(--primary)]/10 text-[var(--primary)]"
                              : "border border-[var(--border)] text-[var(--muted)]"
                          }`}
                        >
                          {paper.has_structured_breakdown
                            ? "Structured data ready"
                            : "Needs extra processing"}
                        </span>
                        <span className="rounded-full border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--muted)]">
                          Added {formatDate(paper.created_at)}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        {compareLoading && (
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] px-6 py-8">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <div className="h-6 w-6 shrink-0 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
              <div>
                <h2 className="text-lg font-semibold">Comparing selected papers</h2>
                <p className="mt-1 text-sm leading-6 text-[var(--muted)]">
                  Normalizing paper evidence, generating missing breakdowns if
                  needed, and building the comparison matrix.
                </p>
              </div>
            </div>
          </section>
        )}

        {compareResult && (
          <section className="space-y-6 border-t border-[var(--border)] pt-8">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <h2 className="text-2xl font-semibold">Compare Results</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Stable rendered output for the current selection. Changing the
                  selection clears the result until you run compare again.
                </p>
              </div>
              <div className="flex flex-col gap-3 xl:items-end">
                <span className="text-sm text-[var(--muted)]">
                  {compareResult.selected_papers.length} papers compared
                </span>
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
                    placeholder="Comparison title"
                    className="w-full min-w-0 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm outline-none transition-colors focus:border-[var(--primary)] sm:min-w-96"
                  />
                  <button
                    onClick={handleSaveComparison}
                    disabled={saveLoading}
                    className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm font-medium transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {saveLoading ? "Saving..." : "Save Comparison"}
                  </button>
                </div>
                {saveError && (
                  <p className="text-sm text-red-500">{saveError}</p>
                )}
                {saveSuccess && (
                  <p className="text-sm text-[var(--primary)]">{saveSuccess}</p>
                )}
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {compareResult.selected_papers.map((paper) => {
                const profile = profileById[paper.id];

                return (
                  <div
                    key={paper.id}
                    className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h3 className="text-lg font-semibold line-clamp-2">
                          {paper.title}
                        </h3>
                        {(paper.authors || profile?.authors) && (
                          <p className="mt-1 text-sm text-[var(--muted)] line-clamp-2">
                            {paper.authors || profile?.authors}
                          </p>
                        )}
                      </div>

                      <a
                        href={`/papers/${paper.id}`}
                        className="shrink-0 text-sm text-[var(--primary)] hover:underline"
                      >
                        Open
                      </a>
                    </div>

                    {profile?.warnings.length ? (
                      <ul className="mt-4 space-y-2 text-sm text-[var(--muted)]">
                        {profile.warnings.map((warning) => (
                          <li key={warning} className="rounded-lg bg-[var(--background)] px-3 py-2">
                            {warning}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-4 text-sm text-[var(--muted)]">
                        No field-level warnings surfaced for this paper.
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            {compareResult.warnings.length > 0 && (
              <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
                <h3 className="text-lg font-semibold">Warnings</h3>
                <ul className="mt-4 space-y-3 text-sm text-[var(--muted)]">
                  {compareResult.warnings.map((warning) => (
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

            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
              <h3 className="text-lg font-semibold">Narrative Summary</h3>
              <div className="mt-4 whitespace-pre-wrap text-sm leading-7">
                {compareResult.narrative_summary}
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
              <div className="border-b border-[var(--border)] px-6 py-5">
                <h3 className="text-lg font-semibold">Comparison Table</h3>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Built for laptop-width horizontal scanning across the selected
                  papers.
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-[960px] w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)]">
                      {compareResult.comparison_table.columns.map((column, index) => (
                        <th
                          key={column.key}
                          className={`px-5 py-4 text-left align-top font-semibold ${
                            index === 0
                              ? "sticky left-0 z-10 min-w-52 bg-[var(--card)]"
                              : "min-w-64"
                          }`}
                        >
                          {column.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {compareResult.comparison_table.rows.map((row) => (
                      <tr key={row.key} className="border-b border-[var(--border)] last:border-b-0">
                        <th className="sticky left-0 z-10 min-w-52 bg-[var(--card)] px-5 py-4 text-left align-top font-medium">
                          {row.label}
                        </th>
                        {row.values.map((value, index) => (
                          <td
                            key={`${row.key}-${compareResult.comparison_table.columns[index + 1]?.key}`}
                            className="min-w-64 px-5 py-4 align-top leading-6 text-[var(--foreground)]/90"
                          >
                            {value}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
        </div>
      }
    >
      <ComparePageContent />
    </Suspense>
  );
}
