"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";

import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DiscoveryResult {
  id: string;
  arxiv_id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  published: string | null;
  relevance_score: number | null;
  relevance_reason: string | null;
  rank_order: number;
  paper_id: string | null;
}

interface DiscoveryRun {
  id: string;
  question: string;
  status: string;
  generated_queries: string[] | null;
  budget_used: {
    queries_generated?: number;
    total_papers_fetched?: number;
    papers_ranked?: number;
    max_results_requested?: number;
    warnings?: string[];
  } | null;
  warnings: string[];
  error_message: string | null;
  created_at: string;
  results: DiscoveryResult[];
}

type IngestStatus = "loading" | "done" | "error";
type IngestingState = Record<
  string,
  {
    status: IngestStatus;
    message?: string;
  }
>;

export default function DiscoverResultsPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.id as string;

  const [run, setRun] = useState<DiscoveryRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [pollAttempt, setPollAttempt] = useState(0);
  const [ingesting, setIngesting] = useState<IngestingState>({});
  const [showQueries, setShowQueries] = useState(false);

  const fetchRun = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/discover/${runId}`);
      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to load discovery run."),
        );
      }
      const data = await res.json();
      setRun({
        ...data,
        warnings: Array.isArray(data.warnings) ? data.warnings : [],
      });
      setLoadError("");
      return data.status;
    } catch (err) {
      setLoadError(
        err instanceof Error ? err.message : "Failed to load discovery run.",
      );
      return null;
    }
  }, [runId]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      const status = await fetchRun();
      setLoading(false);
      if (!cancelled && (status === "pending" || status === "running")) {
        timer = setTimeout(poll, 2000);
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [fetchRun, pollAttempt]);

  const handleRetryLoad = () => {
    setLoading(true);
    setLoadError("");
    setPollAttempt((current) => current + 1);
  };

  const handleIngest = async (resultId: string) => {
    setIngesting((prev) => ({ ...prev, [resultId]: { status: "loading" } }));
    try {
      const res = await fetch(
        `${API_URL}/discover/${runId}/ingest/${resultId}`,
        { method: "POST" }
      );
      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to ingest this paper."),
        );
      }
      const data = await res.json();
      setIngesting((prev) => ({ ...prev, [resultId]: { status: "done" } }));
      setRun((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          results: prev.results.map((r) =>
            r.id === resultId ? { ...r, paper_id: data.paper_id } : r
          ),
        };
      });
    } catch (err) {
      setIngesting((prev) => ({
        ...prev,
        [resultId]: {
          status: "error",
          message:
            err instanceof Error ? err.message : "Failed to ingest this paper.",
        },
      }));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-8 h-8 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-[var(--muted)]">Loading...</p>
        </div>
      </div>
    );
  }

  if (loadError && !run) {
    return (
      <div className="min-h-screen p-8 max-w-3xl mx-auto">
        <a
          href="/"
          className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
        >
          &larr; Back to home
        </a>
        <div className="mt-8 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
          {loadError}
        </div>
        <button
          onClick={handleRetryLoad}
          className="mt-4 rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)]"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-[var(--muted)]">Discovery run not found.</p>
      </div>
    );
  }

  const isRunning = run.status === "pending" || run.status === "running";

  return (
    <div className="min-h-screen px-6 py-12">
      <div className="max-w-3xl mx-auto space-y-8">
        <div>
          <a
            href="/"
            className="text-sm text-[var(--muted)] hover:text-[var(--primary)] transition-colors"
          >
            &larr; Back to home
          </a>
          <h1 className="text-3xl font-bold mt-4 mb-2">{run.question}</h1>

          {loadError && (
            <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
              <p>{loadError}</p>
              <button
                onClick={handleRetryLoad}
                className="mt-3 rounded-lg border border-red-500/30 px-3 py-1.5 font-medium transition-colors hover:bg-red-500/10"
              >
                Retry refresh
              </button>
            </div>
          )}

          {isRunning && (
            <div className="flex items-center gap-3 mt-4 p-4 rounded-lg border border-[var(--border)] bg-[var(--card)]">
              <div className="w-5 h-5 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
              <div>
                <p className="font-medium">
                  {run.status === "pending"
                    ? "Starting discovery..."
                    : "Searching and ranking papers..."}
                </p>
                <p className="text-sm text-[var(--muted)]">
                  Generating queries, searching arXiv, and ranking by relevance
                </p>
              </div>
            </div>
          )}

          {run.status === "failed" && (
            <div className="mt-4 p-4 rounded-lg border border-red-500/30 bg-red-500/5">
              <p className="font-medium text-red-500">Discovery failed</p>
              {run.error_message && (
                <p className="text-sm text-[var(--muted)] mt-1">
                  {run.error_message}
                </p>
              )}
            </div>
          )}
        </div>
        {run.generated_queries && run.generated_queries.length > 0 && (
          <div>
            <button
              onClick={() => setShowQueries(!showQueries)}
              className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
            >
              {showQueries ? "Hide" : "Show"} generated queries (
              {run.generated_queries.length})
            </button>
            {showQueries && (
              <div className="mt-2 p-4 rounded-lg border border-[var(--border)] bg-[var(--card)] space-y-2">
                {run.generated_queries.map((q, i) => (
                  <div
                    key={i}
                    className="text-sm font-mono text-[var(--muted)]"
                  >
                    {i + 1}. {q}
                  </div>
                ))}
                {run.budget_used && (
                  <p className="text-xs text-[var(--muted)] pt-2 border-t border-[var(--border)]">
                    {run.budget_used.total_papers_fetched} papers fetched,{" "}
                    {run.budget_used.papers_ranked} ranked
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {run.warnings.length > 0 && (
          <section className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
            <h2 className="font-semibold text-amber-700">
              Discovery quality notes
            </h2>
            <p className="mt-1 text-[var(--muted)]">
              These notes flag weak coverage or low confidence. Results are
              relevance-ranked arXiv matches, not an exhaustive literature
              review.
            </p>
            <ul className="mt-3 space-y-1 text-amber-700">
              {run.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </section>
        )}

        {run.status === "complete" && run.results.length === 0 && (
          <p className="text-[var(--muted)]">
            No relevant papers found. Try rephrasing your question.
          </p>
        )}

        {run.results.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">
              Results ({run.results.length})
            </h2>
            {run.results.map((result) => {
                const ingestState = ingesting[result.id];

                return (
                  <div
                    key={result.id}
                    className="p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] space-y-3"
                  >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-[var(--primary)]/10 text-[var(--primary)]">
                        #{result.rank_order}
                      </span>
                      {result.relevance_score !== null && (
                        <span
                          className={`text-xs font-medium px-2 py-0.5 rounded ${
                            result.relevance_score >= 0.7
                              ? "bg-green-500/10 text-green-600"
                              : result.relevance_score >= 0.4
                                ? "bg-yellow-500/10 text-yellow-600"
                                : "bg-red-500/10 text-red-500"
                          }`}
                        >
                          {(result.relevance_score * 100).toFixed(0)}% relevant
                        </span>
                      )}
                    </div>
                    <h3 className="font-semibold leading-snug">
                      {result.title}
                    </h3>
                    {result.authors && (
                      <p className="text-sm text-[var(--muted)] mt-1 line-clamp-1">
                        {result.authors}
                      </p>
                    )}
                  </div>
                </div>

                {result.relevance_reason && (
                  <p className="text-sm text-[var(--muted)] italic">
                    {result.relevance_reason}
                  </p>
                )}

                {result.abstract && (
                  <p className="text-sm text-[var(--muted)] line-clamp-3">
                    {result.abstract}
                  </p>
                )}

                <div className="flex items-center gap-3 pt-1">
                  {result.published && (
                    <span className="text-xs text-[var(--muted)]">
                      {result.published}
                    </span>
                  )}
                  <a
                    href={`https://arxiv.org/abs/${result.arxiv_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-[var(--primary)] hover:underline"
                  >
                    arXiv:{result.arxiv_id}
                  </a>

                  {result.paper_id ? (
                    <button
                      onClick={() =>
                        router.push(`/papers/${result.paper_id}`)
                      }
                      className="ml-auto text-sm px-4 py-1.5 rounded-lg bg-green-500/10 text-green-600 font-medium"
                    >
                      View Paper
                    </button>
                  ) : ingestState?.status === "loading" ? (
                    <span className="ml-auto inline-flex items-center gap-2 text-sm text-[var(--muted)]">
                      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                      Ingesting...
                    </span>
                  ) : ingestState?.status === "error" ? (
                    <button
                      onClick={() => handleIngest(result.id)}
                      className="ml-auto text-sm px-4 py-1.5 rounded-lg bg-red-500/10 text-red-500 font-medium"
                    >
                      Retry
                    </button>
                  ) : (
                    <button
                      onClick={() => handleIngest(result.id)}
                      className="ml-auto text-sm px-4 py-1.5 rounded-lg bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white font-medium transition-colors"
                    >
                      Ingest
                    </button>
                  )}
                </div>

                {ingestState?.status === "error" && (
                  <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
                    {ingestState.message || "Failed to ingest this paper."}
                  </div>
                )}
              </div>
                );
              })}
          </div>
        )}
      </div>
    </div>
  );
}
