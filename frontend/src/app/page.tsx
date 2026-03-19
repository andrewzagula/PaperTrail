"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PaperItem {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
}

export default function Home() {
  const router = useRouter();
  const [papers, setPapers] = useState<PaperItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/papers/`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setPapers(data))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center px-6 py-16">
      <main className="max-w-2xl w-full text-center space-y-8">
        <h1 className="text-5xl font-bold tracking-tight">
          Paper<span className="text-[var(--primary)]">trail</span>
        </h1>
        <p className="text-xl text-[var(--muted)] leading-relaxed">
          Go from paper to understanding to comparison to idea to
          implementation.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4">
          {[
            {
              title: "Understand",
              desc: "Structured breakdowns of any research paper",
            },
            {
              title: "Compare",
              desc: "Side-by-side analysis of multiple papers",
            },
            {
              title: "Ideate",
              desc: "Generate novel research ideas from literature",
            },
            {
              title: "Implement",
              desc: "Turn methods into runnable Python code",
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

        <div className="pt-6">
          <button
            onClick={() => router.push("/papers/new")}
            className="px-8 py-3 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white rounded-lg font-medium transition-colors"
          >
            Upload a Paper
          </button>
        </div>

        {/* Paper library */}
        {loaded && papers.length > 0 && (
          <div className="pt-8 text-left">
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
