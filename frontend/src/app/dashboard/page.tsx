"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface WorkspaceCounts {
  papers: number;
  discovery_runs: number;
  saved_items: number;
  saved_comparisons: number;
  saved_ideas: number;
  saved_implementations: number;
}

interface WorkspacePaper {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
  has_structured_breakdown: boolean;
  embedding_status: string;
  embedding_provider: string;
  embedding_model: string;
  embedded_at: string | null;
}

interface WorkspaceDiscoveryRun {
  id: string;
  question: string;
  status: string;
  created_at: string;
  num_results: number;
}

interface WorkspaceSourcePaper {
  id: string;
  title: string;
  authors: string | null;
  arxiv_url: string | null;
  created_at: string;
}

interface WorkspaceSavedItem {
  id: string;
  title: string;
  item_type: string;
  paper_ids: string[];
  created_at: string;
  source_papers: WorkspaceSourcePaper[];
}

interface WorkspaceSummary {
  counts: WorkspaceCounts;
  recent_papers: WorkspacePaper[];
  recent_discovery_runs: WorkspaceDiscoveryRun[];
  recent_saved_items: WorkspaceSavedItem[];
}

const COUNT_CARDS: {
  key: keyof WorkspaceCounts;
  label: string;
  detail: string;
}[] = [
  { key: "papers", label: "Papers", detail: "In library" },
  { key: "discovery_runs", label: "Discovery Runs", detail: "Research searches" },
  {
    key: "saved_comparisons",
    label: "Comparisons",
    detail: "Saved compare results",
  },
  { key: "saved_ideas", label: "Ideas", detail: "Saved idea runs" },
  {
    key: "saved_implementations",
    label: "Implementations",
    detail: "Saved code plans",
  },
  { key: "saved_items", label: "Saved Items", detail: "Total saved work" },
];

const TYPE_LABELS: Record<string, string> = {
  comparison: "Comparison",
  idea: "Idea",
  implementation: "Implementation",
};

const STATUS_LABELS: Record<string, string> = {
  complete: "Complete",
  running: "Running",
  pending: "Pending",
  failed: "Failed",
};

function formatDate(value: string | null): string {
  if (!value) {
    return "Unknown date";
  }

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

function formatType(value: string): string {
  return TYPE_LABELS[value] || value.replace(/_/g, " ");
}

function formatStatus(value: string): string {
  return STATUS_LABELS[value] || value;
}

function statusClassName(status: string): string {
  if (status === "complete" || status === "ready") {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-600";
  }

  if (status === "running" || status === "pending") {
    return "border-amber-500/20 bg-amber-500/10 text-amber-600";
  }

  if (status === "failed") {
    return "border-red-500/20 bg-red-500/10 text-red-500";
  }

  return "border-[var(--border)] bg-[var(--card)] text-[var(--muted)]";
}

function typeClassName(itemType: string): string {
  if (itemType === "comparison") {
    return "border-blue-500/20 bg-blue-500/10 text-blue-600";
  }

  if (itemType === "idea") {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-600";
  }

  if (itemType === "implementation") {
    return "border-amber-500/20 bg-amber-500/10 text-amber-600";
  }

  return "border-[var(--border)] bg-[var(--card)] text-[var(--muted)]";
}

function isEmptyWorkspace(summary: WorkspaceSummary): boolean {
  return (
    summary.counts.papers === 0 &&
    summary.counts.discovery_runs === 0 &&
    summary.counts.saved_items === 0
  );
}

function LoadingState() {
  return (
    <div className="min-h-screen px-6 py-10">
      <main className="mx-auto w-full max-w-6xl space-y-8">
        <div className="space-y-3">
          <div className="h-5 w-28 rounded-lg bg-[var(--border)]" />
          <div className="h-10 w-64 rounded-lg bg-[var(--border)]" />
          <div className="h-5 w-full max-w-xl rounded-lg bg-[var(--border)]" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="h-28 rounded-lg border border-[var(--border)] bg-[var(--card)]"
            />
          ))}
        </div>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.8fr)]">
          <div className="space-y-4">
            <div className="h-7 w-40 rounded-lg bg-[var(--border)]" />
            <div className="h-24 rounded-lg border border-[var(--border)] bg-[var(--card)]" />
            <div className="h-24 rounded-lg border border-[var(--border)] bg-[var(--card)]" />
          </div>
          <div className="space-y-4">
            <div className="h-7 w-40 rounded-lg bg-[var(--border)]" />
            <div className="h-28 rounded-lg border border-[var(--border)] bg-[var(--card)]" />
          </div>
        </div>
      </main>
    </div>
  );
}

function EmptyWorkspaceState() {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6">
      <h2 className="text-xl font-semibold">Start a local research workspace</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
        Begin with a research question, upload a paper directly, or open one of
        the saved-work flows once your library has papers.
      </p>
      <div className="mt-5 flex flex-wrap gap-3 text-sm">
        <Link
          href="/"
          className="rounded-lg bg-[var(--primary)] px-4 py-2 font-medium text-white transition-colors hover:bg-[var(--primary-hover)]"
        >
          Start Discovery
        </Link>
        <Link
          href="/papers/new"
          className="rounded-lg border border-[var(--border)] px-4 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
        >
          Upload Paper
        </Link>
        <Link
          href="/compare"
          className="rounded-lg border border-[var(--border)] px-4 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
        >
          Compare Library
        </Link>
        <Link
          href="/ideas"
          className="rounded-lg border border-[var(--border)] px-4 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
        >
          Generate Ideas
        </Link>
      </div>
    </div>
  );
}

function SectionEmptyState({
  title,
  href,
  action,
}: {
  title: string;
  href: string;
  action: string;
}) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--border)] p-5 text-sm text-[var(--muted)]">
      <p>{title}</p>
      <Link
        href={href}
        className="mt-3 inline-flex rounded-lg border border-[var(--border)] px-3 py-2 font-medium text-[var(--foreground)] transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
      >
        {action}
      </Link>
    </div>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<WorkspaceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [renameError, setRenameError] = useState("");
  const [renamingItemId, setRenamingItemId] = useState<string | null>(null);
  const [deleteConfirmItemId, setDeleteConfirmItemId] = useState<string | null>(
    null,
  );
  const [deleteError, setDeleteError] = useState("");
  const [deletingItemId, setDeletingItemId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState("");

  const loadSummary = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }
    setError("");

    try {
      const res = await fetch(`${API_URL}/workspace/summary`);
      if (!res.ok) {
        throw new Error("Failed to load workspace summary.");
      }

      const data: WorkspaceSummary = await res.json();
      setSummary(data);
    } catch (err) {
      setSummary(null);
      setError(
        err instanceof Error ? err.message : "Failed to load workspace summary.",
      );
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const savedItemsByType = useMemo(() => {
    const grouped: Record<string, WorkspaceSavedItem[]> = {};

    for (const item of summary?.recent_saved_items || []) {
      if (!grouped[item.item_type]) {
        grouped[item.item_type] = [];
      }
      grouped[item.item_type].push(item);
    }

    return grouped;
  }, [summary]);

  const beginRename = (item: WorkspaceSavedItem) => {
    setEditingItemId(item.id);
    setRenameTitle(item.title);
    setRenameError("");
    setDeleteError("");
    setDeleteConfirmItemId(null);
    setActionMessage("");
  };

  const cancelRename = () => {
    setEditingItemId(null);
    setRenameTitle("");
    setRenameError("");
  };

  const renameItem = async (item: WorkspaceSavedItem) => {
    const title = renameTitle.trim();
    if (!title) {
      setRenameError("Saved item title is required.");
      return;
    }

    setRenamingItemId(item.id);
    setRenameError("");
    setActionMessage("");

    try {
      const res = await fetch(`${API_URL}/workspace/saved-items/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });

      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to rename saved artifact."),
        );
      }

      cancelRename();
      setActionMessage("Saved artifact renamed.");
      await loadSummary(false);
    } catch (err) {
      setRenameError(
        err instanceof Error ? err.message : "Failed to rename saved artifact.",
      );
    } finally {
      setRenamingItemId(null);
    }
  };

  const requestDelete = (item: WorkspaceSavedItem) => {
    setDeleteConfirmItemId(item.id);
    setDeleteError("");
    setEditingItemId(null);
    setRenameError("");
    setActionMessage("");
  };

  const cancelDelete = () => {
    setDeleteConfirmItemId(null);
    setDeleteError("");
  };

  const deleteItem = async (item: WorkspaceSavedItem) => {
    setDeletingItemId(item.id);
    setDeleteError("");
    setActionMessage("");

    try {
      const res = await fetch(`${API_URL}/workspace/saved-items/${item.id}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to delete saved artifact."),
        );
      }

      cancelDelete();
      setActionMessage("Saved artifact deleted.");
      await loadSummary(false);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete saved artifact.",
      );
    } finally {
      setDeletingItemId(null);
    }
  };

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return (
      <div className="min-h-screen px-6 py-10">
        <main className="mx-auto flex min-h-[60vh] w-full max-w-3xl items-center">
          <div className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-6">
            <p className="text-sm font-medium text-red-500">Workspace unavailable</p>
            <h1 className="mt-2 text-2xl font-semibold">Could not load dashboard</h1>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{error}</p>
            <div className="mt-5 flex flex-wrap gap-3 text-sm">
              <button
                type="button"
                onClick={() => loadSummary()}
                className="rounded-lg bg-[var(--primary)] px-4 py-2 font-medium text-white transition-colors hover:bg-[var(--primary-hover)]"
              >
                Retry
              </button>
              <Link
                href="/"
                className="rounded-lg border border-[var(--border)] px-4 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
              >
                Back Home
              </Link>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (!summary) {
    return null;
  }

  return (
    <div className="min-h-screen px-6 py-10">
      <main className="mx-auto w-full max-w-6xl space-y-8">
        <header className="space-y-5">
          <div>
            <Link
              href="/"
              className="text-sm font-medium text-[var(--primary)] transition-colors hover:text-[var(--primary-hover)]"
            >
              Papertrail
            </Link>
            <h1 className="mt-3 text-4xl font-bold tracking-tight">Workspace</h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-[var(--muted)]">
              A local home base for papers, discovery runs, and saved research
              outputs.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link
              href="/"
              className="rounded-lg bg-[var(--primary)] px-4 py-2 font-medium text-white transition-colors hover:bg-[var(--primary-hover)]"
            >
              Start Discovery
            </Link>
            <Link
              href="/papers/new"
              className="rounded-lg border border-[var(--border)] px-4 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
            >
              Upload Paper
            </Link>
            <Link
              href="/compare"
              className="rounded-lg border border-[var(--border)] px-4 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
            >
              Compare Library
            </Link>
            <Link
              href="/ideas"
              className="rounded-lg border border-[var(--border)] px-4 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
            >
              Generate Ideas
            </Link>
          </div>
        </header>

        {isEmptyWorkspace(summary) ? (
          <EmptyWorkspaceState />
        ) : (
          <>
            <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {COUNT_CARDS.map((card) => (
                <div
                  key={card.key}
                  className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5"
                >
                  <p className="text-sm text-[var(--muted)]">{card.label}</p>
                  <p className="mt-3 text-3xl font-semibold">
                    {summary.counts[card.key]}
                  </p>
                  <p className="mt-1 text-xs uppercase text-[var(--muted)]">
                    {card.detail}
                  </p>
                </div>
              ))}
            </section>

            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.8fr)]">
              <div className="space-y-8">
                <section className="space-y-4">
                  <div className="flex items-center justify-between gap-4">
                    <h2 className="text-xl font-semibold">Recent Papers</h2>
                    <Link
                      href="/papers/new"
                      className="text-sm font-medium text-[var(--primary)] transition-colors hover:text-[var(--primary-hover)]"
                    >
                      Add paper
                    </Link>
                  </div>
                  {summary.recent_papers.length === 0 ? (
                    <SectionEmptyState
                      title="No papers have been added yet."
                      href="/papers/new"
                      action="Upload Paper"
                    />
                  ) : (
                    <div className="space-y-3">
                      {summary.recent_papers.map((paper) => (
                        <Link
                          key={paper.id}
                          href={`/papers/${paper.id}`}
                          className="block rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:border-[var(--primary)]/40"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <h3 className="line-clamp-2 font-medium">
                                {paper.title}
                              </h3>
                              {paper.authors && (
                                <p className="mt-1 line-clamp-1 text-sm text-[var(--muted)]">
                                  {paper.authors}
                                </p>
                              )}
                            </div>
                            <span className="text-xs text-[var(--muted)]">
                              {formatDate(paper.created_at)}
                            </span>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2 text-xs">
                            <span
                              className={`rounded-full border px-2.5 py-1 ${statusClassName(
                                paper.embedding_status,
                              )}`}
                            >
                              Embeddings {paper.embedding_status}
                            </span>
                            <span
                              className={`rounded-full border px-2.5 py-1 ${
                                paper.has_structured_breakdown
                                  ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-600"
                                  : "border-[var(--border)] bg-[var(--card)] text-[var(--muted)]"
                              }`}
                            >
                              {paper.has_structured_breakdown
                                ? "Analyzed"
                                : "Needs analysis"}
                            </span>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </section>

                <section className="space-y-4">
                  <div className="flex items-center justify-between gap-4">
                    <h2 className="text-xl font-semibold">Recent Discoveries</h2>
                    <Link
                      href="/"
                      className="text-sm font-medium text-[var(--primary)] transition-colors hover:text-[var(--primary-hover)]"
                    >
                      New search
                    </Link>
                  </div>
                  {summary.recent_discovery_runs.length === 0 ? (
                    <SectionEmptyState
                      title="No discovery runs yet."
                      href="/"
                      action="Start Discovery"
                    />
                  ) : (
                    <div className="space-y-3">
                      {summary.recent_discovery_runs.map((run) => (
                        <Link
                          key={run.id}
                          href={`/discover/${run.id}`}
                          className="block rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:border-[var(--primary)]/40"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <h3 className="min-w-0 flex-1 line-clamp-2 font-medium">
                              {run.question}
                            </h3>
                            <span
                              className={`rounded-full border px-2.5 py-1 text-xs ${statusClassName(
                                run.status,
                              )}`}
                            >
                              {formatStatus(run.status)}
                            </span>
                          </div>
                          <p className="mt-2 text-sm text-[var(--muted)]">
                            {run.status === "complete"
                              ? `${run.num_results} papers found`
                              : `${run.num_results} results recorded`}{" "}
                            on {formatDate(run.created_at)}
                          </p>
                        </Link>
                      ))}
                    </div>
                  )}
                </section>
              </div>

              <aside className="space-y-4">
                <div className="flex items-center justify-between gap-4">
                  <h2 className="text-xl font-semibold">Recent Saved Work</h2>
                  {actionMessage && (
                    <span className="text-sm font-medium text-emerald-600">
                      {actionMessage}
                    </span>
                  )}
                </div>
                {summary.recent_saved_items.length === 0 ? (
                  <SectionEmptyState
                    title="No saved comparisons, ideas, or implementation outputs yet."
                    href="/compare"
                    action="Compare Library"
                  />
                ) : (
                  <div className="space-y-5">
                    {Object.entries(savedItemsByType).map(([itemType, items]) => (
                      <section key={itemType} className="space-y-3">
                        <h3 className="text-sm font-semibold uppercase text-[var(--muted)]">
                          {formatType(itemType)}
                        </h3>
                        {items.map((item) => (
                          <article
                            key={item.id}
                            className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span
                                className={`rounded-full border px-2.5 py-1 text-xs ${typeClassName(
                                  item.item_type,
                                )}`}
                              >
                                {formatType(item.item_type)}
                              </span>
                              <span className="text-xs text-[var(--muted)]">
                                {formatDate(item.created_at)}
                              </span>
                            </div>
                            {editingItemId === item.id ? (
                              <form
                                className="mt-4 space-y-3"
                                onSubmit={(event) => {
                                  event.preventDefault();
                                  renameItem(item);
                                }}
                              >
                                <label
                                  htmlFor={`rename-${item.id}`}
                                  className="sr-only"
                                >
                                  Saved artifact title
                                </label>
                                <input
                                  id={`rename-${item.id}`}
                                  value={renameTitle}
                                  onChange={(event) =>
                                    setRenameTitle(event.target.value)
                                  }
                                  disabled={renamingItemId === item.id}
                                  maxLength={1000}
                                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none transition-colors focus:border-[var(--primary)]"
                                />
                                {renameError && (
                                  <p className="text-sm text-red-500">
                                    {renameError}
                                  </p>
                                )}
                                <div className="flex flex-wrap gap-2 text-sm">
                                  <button
                                    type="submit"
                                    disabled={renamingItemId === item.id}
                                    className="rounded-lg bg-[var(--primary)] px-3 py-2 font-medium text-white transition-colors hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    {renamingItemId === item.id
                                      ? "Saving..."
                                      : "Save"}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={cancelRename}
                                    disabled={renamingItemId === item.id}
                                    className="rounded-lg border border-[var(--border)] px-3 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </form>
                            ) : (
                              <>
                                <Link
                                  href={`/dashboard/saved/${item.id}`}
                                  className="mt-3 block transition-colors hover:text-[var(--primary)]"
                                >
                                  <h4 className="line-clamp-2 font-medium">
                                    {item.title}
                                  </h4>
                                </Link>
                                {item.source_papers.length > 0 ? (
                                  <p className="mt-2 line-clamp-2 text-sm text-[var(--muted)]">
                                    {item.source_papers
                                      .map((paper) => paper.title)
                                      .join(", ")}
                                  </p>
                                ) : (
                                  <p className="mt-2 text-sm text-[var(--muted)]">
                                    Source papers unavailable
                                  </p>
                                )}
                                <div className="mt-4 flex flex-wrap gap-2 text-sm">
                                  <Link
                                    href={`/dashboard/saved/${item.id}`}
                                    className="rounded-lg border border-[var(--border)] px-3 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
                                  >
                                    Open
                                  </Link>
                                  <button
                                    type="button"
                                    onClick={() => beginRename(item)}
                                    disabled={deletingItemId === item.id}
                                    className="rounded-lg border border-[var(--border)] px-3 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    Rename
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => requestDelete(item)}
                                    disabled={deletingItemId === item.id}
                                    className="rounded-lg border border-red-500/30 px-3 py-2 font-medium text-red-500 transition-colors hover:border-red-500 hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    Delete
                                  </button>
                                </div>
                              </>
                            )}
                            {deleteConfirmItemId === item.id && (
                              <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3">
                                <p className="text-sm font-medium text-red-600">
                                  Delete this saved artifact?
                                </p>
                                <p className="mt-1 text-sm leading-6 text-red-600">
                                  Source papers and generated workflow history
                                  will stay in the workspace.
                                </p>
                                {deleteError && (
                                  <p className="mt-2 text-sm text-red-600">
                                    {deleteError}
                                  </p>
                                )}
                                <div className="mt-3 flex flex-wrap gap-2 text-sm">
                                  <button
                                    type="button"
                                    onClick={() => deleteItem(item)}
                                    disabled={deletingItemId === item.id}
                                    className="rounded-lg bg-red-600 px-3 py-2 font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    {deletingItemId === item.id
                                      ? "Deleting..."
                                      : "Delete"}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={cancelDelete}
                                    disabled={deletingItemId === item.id}
                                    className="rounded-lg border border-red-500/30 px-3 py-2 font-medium text-red-600 transition-colors hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            )}
                          </article>
                        ))}
                      </section>
                    ))}
                  </div>
                )}
              </aside>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
