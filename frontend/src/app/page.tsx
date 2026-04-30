"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PaperItem {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
}

interface DiscoveryRunItem {
  id: string;
  question: string;
  status: string;
  created_at: string;
  num_results: number;
}

export default function Home() {
  const router = useRouter();
  const [papers, setPapers] = useState<PaperItem[]>([]);
  const [runs, setRuns] = useState<DiscoveryRunItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/papers/`)
        .then((res) => (res.ok ? res.json() : []))
        .catch(() => []),
      fetch(`${API_URL}/discover/`)
        .then((res) => (res.ok ? res.json() : []))
        .catch(() => []),
    ]).then(([papersData, runsData]) => {
      setPapers(papersData);
      setRuns(runsData);
      setLoaded(true);
    });
  }, []);

  const handleDiscover = async () => {
    if (!question.trim() || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/discover/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim(), max_results: 10 }),
      });
      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Discovery request failed"),
        );
      }
      const data = await res.json();
      router.push(`/discover/${data.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center px-6 py-16">
      <main className="max-w-2xl w-full text-center space-y-8">
        <h1 className="text-5xl font-bold tracking-tight">
          Paper<span className="text-[var(--primary)]">trail</span>
        </h1>
        <p className="text-xl text-[var(--muted)] leading-relaxed">
          Start with a research question. Discover, understand, compare, and
          generate ideas.
        </p>
        <div className="pt-2">
          <div className="flex gap-3">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !submitting) {
                  handleDiscover();
                }
              }}
              placeholder="What is your research question?"
              className="flex-1 px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--foreground)] placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--primary)] transition-colors"
              disabled={submitting}
            />
            <button
              onClick={handleDiscover}
              disabled={submitting || !question.trim()}
              className="px-6 py-3 bg-[var(--primary)] hover:bg-[var(--primary-hover)] disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
            >
              {submitting ? "Searching..." : "Discover"}
            </button>
          </div>
          {error && (
            <p className="text-red-500 text-sm mt-2 text-left">{error}</p>
          )}
          <div className="mt-3 flex flex-wrap gap-3 text-sm">
            <a
              href="/dashboard"
              className="rounded-lg border border-[var(--primary)]/20 bg-[var(--primary)]/5 px-4 py-2 text-[var(--primary)] transition-colors hover:bg-[var(--primary)]/10"
            >
              Workspace
            </a>
            <a
              href="/papers/new"
              className="rounded-lg border border-[var(--border)] px-4 py-2 text-[var(--foreground)] transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)]"
            >
              Upload Paper
            </a>
            <a
              href="/compare"
              className="rounded-lg border border-[var(--primary)]/20 bg-[var(--primary)]/5 px-4 py-2 text-[var(--primary)] transition-colors hover:bg-[var(--primary)]/10"
            >
              Compare Library
            </a>
            <a
              href="/ideas"
              className="rounded-lg border border-[var(--primary)]/20 bg-[var(--primary)]/5 px-4 py-2 text-[var(--primary)] transition-colors hover:bg-[var(--primary)]/10"
            >
              Generate Ideas
            </a>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4">
          {[
            {
              title: "Discover",
              desc: "Find relevant papers from a research question",
            },
            {
              title: "Understand",
              desc: "Structured breakdowns of any research paper",
            },
            {
              title: "Compare",
              desc: "Side-by-side analysis of multiple papers",
            },
            {
              title: "Ideas",
              desc: "Generate grounded research directions from papers or topics",
            },
          ].map((item) => (
            <div
              key={item.title}
              className="p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] text-left"
            >
              <h3 className="font-semibold text-lg mb-1">{item.title}</h3>
              <p className="text-sm text-[var(--muted)]">{item.desc}</p>
            </div>
          ))}
        </div>
        {loaded && runs.length > 0 && (
          <div className="pt-6 text-left">
            <h2 className="text-lg font-semibold mb-4">Recent Discoveries</h2>
            <div className="space-y-3">
              {runs.map((run) => (
                <button
                  key={run.id}
                  onClick={() => router.push(`/discover/${run.id}`)}
                  className="w-full text-left p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] hover:border-[var(--primary)]/30 transition-colors"
                >
                  <h3 className="font-medium mb-1 line-clamp-1">
                    {run.question}
                  </h3>
                  <p className="text-sm text-[var(--muted)]">
                    {run.status === "complete"
                      ? `${run.num_results} papers found`
                      : run.status === "running"
                        ? "Searching..."
                        : run.status === "failed"
                          ? "Failed"
                          : "Pending..."}
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}
        {loaded && papers.length > 0 && (
          <div className="pt-6 text-left">
            <h2 className="text-lg font-semibold mb-4">Your Papers</h2>
            <div className="space-y-3">
              {papers.map((paper) => (
                <button
                  key={paper.id}
                  onClick={() => router.push(`/papers/${paper.id}`)}
                  className="w-full text-left p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] hover:border-[var(--primary)]/30 transition-colors"
                >
                  <h3 className="font-medium mb-1 line-clamp-1">
                    {paper.title}
                  </h3>
                  {paper.authors && (
                    <p className="text-sm text-[var(--muted)] line-clamp-1">
                      {paper.authors}
                    </p>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
