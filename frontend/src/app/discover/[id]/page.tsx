"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";

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
  budget_used: { queries_generated?: number; total_papers_fetched?: number; papers_ranked?: number } | null;
  error_message: string | null;
  created_at: string;
  results: DiscoveryResult[];
}

type IngestingState = Record<string, "loading" | "done" | "error">;

export default function DiscoverResultsPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.id as string;

  const [run, setRun] = useState<DiscoveryRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState<IngestingState>({});
  const [showQueries, setShowQueries] = useState(false);

  const fetchRun = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/discover/${runId}`);
      if (!res.ok) return;
      const data = await res.json();
      setRun(data);
      return data.status;
    } catch {
      // ignore
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
  }, [fetchRun]);

  const handleIngest = async (resultId: string) => {
    setIngesting((prev) => ({ ...prev, [resultId]: "loading" }));
    try {
      const res = await fetch(
        `${API_URL}/discover/${runId}/ingest/${resultId}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error();
      const data = await res.json();
      setIngesting((prev) => ({ ...prev, [resultId]: "done" }));
      // Update result's paper_id locally
      setRun((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          results: prev.results.map((r) =>
            r.id === resultId ? { ...r, paper_id: data.paper_id } : r
          ),
        };
      });
    } catch {
      setIngesting((prev) => ({ ...prev, [resultId]: "error" }));
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
        {/* Header */}
        <div>
          <a
            href="/"
            className="text-sm text-[var(--muted)] hover:text-[var(--primary)] transition-colors"
          >
            &larr; Back to home
          </a>
          <h1 className="text-3xl font-bold mt-4 mb-2">{run.question}</h1>

          {/* Status */}
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

        {/* Generated queries (collapsible) */}
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

        {/* Results */}
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
            {run.results.map((result) => (
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
                  ) : ingesting[result.id] === "loading" ? (
                    <span className="ml-auto text-sm text-[var(--muted)]">
                      Ingesting...
                    </span>
                  ) : ingesting[result.id] === "error" ? (
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
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
