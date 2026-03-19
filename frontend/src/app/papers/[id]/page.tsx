"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Section {
  id: string;
  section_title: string;
  section_order: number;
  content: string;
}

interface Paper {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
  sections: Section[];
}

export default function PaperView() {
  const params = useParams();
  const paperId = params.id as string;

  const [paper, setPaper] = useState<Paper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState<string | null>(null);

  useEffect(() => {
    async function fetchPaper() {
      try {
        const res = await fetch(`${API_URL}/papers/${paperId}`);
        if (!res.ok) throw new Error("Paper not found");
        const data = await res.json();
        setPaper(data);
        if (data.sections.length > 0) {
          setActiveSection(data.sections[0].id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load paper");
      } finally {
        setLoading(false);
      }
    }

    fetchPaper();
  }, [paperId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !paper) {
    return (
      <div className="min-h-screen p-8 max-w-3xl mx-auto">
        <a
          href="/"
          className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
        >
          &larr; Back
        </a>
        <div className="mt-8 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400">
          {error || "Paper not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="border-b border-[var(--border)] p-8">
        <div className="max-w-5xl mx-auto">
          <a
            href="/"
            className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
          >
            &larr; Back
          </a>

          <h1 className="text-3xl font-bold mt-4 mb-2">{paper.title}</h1>

          {paper.authors && (
            <p className="text-[var(--muted)] text-sm mb-3">{paper.authors}</p>
          )}

          {paper.arxiv_url && (
            <a
              href={paper.arxiv_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-[var(--primary)] hover:underline"
            >
              View on arXiv
            </a>
          )}

          {paper.abstract && (
            <div className="mt-4 p-4 rounded-lg bg-[var(--card)] border border-[var(--border)]">
              <h3 className="text-sm font-semibold mb-2 text-[var(--muted)] uppercase tracking-wide">
                Abstract
              </h3>
              <p className="text-sm leading-relaxed">{paper.abstract}</p>
            </div>
          )}
        </div>
      </div>

      {/* Sections */}
      <div className="max-w-5xl mx-auto flex gap-6 p-8">
        {/* Section nav */}
        <nav className="w-56 shrink-0 sticky top-8 self-start">
          <h3 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-3">
            Sections
          </h3>
          <ul className="space-y-1">
            {paper.sections.map((section) => (
              <li key={section.id}>
                <button
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    activeSection === section.id
                      ? "bg-[var(--primary)]/10 text-[var(--primary)] font-medium"
                      : "text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--card)]"
                  }`}
                >
                  {section.section_title}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Section content */}
        <div className="flex-1 min-w-0">
          {paper.sections.map((section) => (
            <div
              key={section.id}
              id={`section-${section.id}`}
              className={`mb-8 p-6 rounded-xl border transition-all ${
                activeSection === section.id
                  ? "border-[var(--primary)]/30 bg-[var(--card)]"
                  : "border-[var(--border)] bg-[var(--card)]"
              }`}
            >
              <h2 className="text-xl font-semibold mb-4">
                {section.section_title}
              </h2>
              <div className="text-sm leading-relaxed whitespace-pre-wrap text-[var(--foreground)]/85">
                {section.content}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
