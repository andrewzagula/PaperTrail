"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { addPaperToCompare } from "@/lib/compare-selection";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: { section_title: string; excerpt: string; section_id?: string }[] | null;
  created_at: string;
}

interface Section {
  id: string;
  section_title: string;
  section_order: number;
  content: string;
}

interface Breakdown {
  problem: string;
  method: string;
  key_contributions: string;
  results: string;
  limitations: string;
  future_work: string;
}

interface Paper {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
  structured_breakdown: Breakdown | null;
  sections: Section[];
}

const BREAKDOWN_LABELS: { key: keyof Breakdown; label: string }[] = [
  { key: "problem", label: "Problem" },
  { key: "method", label: "Method" },
  { key: "key_contributions", label: "Key Contributions" },
  { key: "results", label: "Results" },
  { key: "limitations", label: "Limitations" },
  { key: "future_work", label: "Future Work" },
];

export default function PaperView() {
  const params = useParams();
  const router = useRouter();
  const paperId = params.id as string;

  const [paper, setPaper] = useState<Paper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistoryLoaded, setChatHistoryLoaded] = useState(false);
  const [compareNotice, setCompareNotice] = useState<{
    tone: "info" | "warning";
    message: string;
  } | null>(null);

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

  const handleAnalyze = async () => {
    if (!paper) return;
    setAnalyzing(true);
    setAnalyzeError("");
    try {
      const res = await fetch(`${API_URL}/papers/${paperId}/analyze`, {
        method: "POST",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Analysis failed");
      }
      const breakdown = await res.json();
      setPaper({ ...paper, structured_breakdown: breakdown });
    } catch (err) {
      setAnalyzeError(
        err instanceof Error ? err.message : "Analysis failed"
      );
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAddToCompare = () => {
    if (!paper) return;

    const result = addPaperToCompare(paper.id);

    if (result.added) {
      setCompareNotice({
        tone: "info",
        message:
          result.ids.length >= 2
            ? `Added to compare list. ${result.ids.length} papers are ready to compare.`
            : "Added to compare list. Add one more paper to run a comparison.",
      });
      return;
    }

    if (result.reason === "duplicate") {
      setCompareNotice({
        tone: "info",
        message: "This paper is already in your compare list.",
      });
      return;
    }

    setCompareNotice({
      tone: "warning",
      message: "Your compare list already has 5 papers. Open compare to adjust the selection.",
    });
  };

  const handleComparePapers = () => {
    if (!paper) return;
    router.push(`/compare?paper=${paper.id}`);
  };

  const handleGenerateIdeas = () => {
    if (!paper) return;
    router.push(`/ideas?paper=${encodeURIComponent(paper.id)}`);
  };

  useEffect(() => {
    if (!chatOpen || chatHistoryLoaded) return;
    async function loadHistory() {
      try {
        const res = await fetch(`${API_URL}/papers/${paperId}/chats`);
        if (res.ok) {
          const data = await res.json();
          setChatMessages(data);
        }
      } catch {}
      setChatHistoryLoaded(true);
    }
    loadHistory();
  }, [chatOpen, chatHistoryLoaded, paperId]);

  const handleChatSend = async () => {
    const message = chatInput.trim();
    if (!message || chatLoading) return;

    const userMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: message,
      citations: null,
      created_at: new Date().toISOString(),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setChatLoading(true);

    try {
      const res = await fetch(`${API_URL}/papers/${paperId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Chat failed");
      }
      const data: ChatMessage = await res.json();
      setChatMessages((prev) => [...prev, data]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: err instanceof Error ? err.message : "Something went wrong",
          citations: null,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleClearChat = async () => {
    try {
      await fetch(`${API_URL}/papers/${paperId}/chats`, { method: "DELETE" });
      setChatMessages([]);
    } catch {}
  };

  const scrollToSection = (sectionId: string) => {
    setActiveSection(sectionId);
    const el = document.getElementById(`section-${sectionId}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

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
      <div className="border-b border-[var(--border)] p-8">
        <div className="max-w-5xl mx-auto">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <a
              href="/"
              className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
            >
              &larr; Back
            </a>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={handleAddToCompare}
                className="px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium text-[var(--foreground)] hover:border-[var(--primary)]/30 hover:text-[var(--primary)] transition-colors"
              >
                Add to Compare
              </button>
              <button
                onClick={handleComparePapers}
                className="px-4 py-2 rounded-lg border border-[var(--primary)]/20 bg-[var(--primary)]/5 text-sm font-medium text-[var(--primary)] hover:bg-[var(--primary)]/10 transition-colors"
              >
                Compare Papers
              </button>
              <button
                onClick={handleGenerateIdeas}
                className="px-4 py-2 rounded-lg border border-[var(--primary)]/20 bg-[var(--primary)]/5 text-sm font-medium text-[var(--primary)] hover:bg-[var(--primary)]/10 transition-colors"
              >
                Generate Ideas
              </button>
              <button
                onClick={() => setChatOpen(!chatOpen)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  chatOpen
                    ? "bg-[var(--primary)] text-white"
                    : "border border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--foreground)]/20"
                }`}
              >
                {chatOpen ? "Close Chat" : "Ask Questions"}
              </button>
            </div>
          </div>

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

          {compareNotice && (
            <div
              className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
                compareNotice.tone === "warning"
                  ? "border-red-500/20 bg-red-500/10 text-red-500"
                  : "border-[var(--border)] bg-[var(--card)] text-[var(--foreground)]"
              }`}
            >
              {compareNotice.message}
            </div>
          )}
        </div>
      </div>
      <div className="max-w-5xl mx-auto px-8 pt-8">
        {paper.structured_breakdown ? (
          <div className="mb-8">
            <h2 className="text-lg font-semibold mb-4">Structured Breakdown</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {BREAKDOWN_LABELS.map(({ key, label }) => (
                <div
                  key={key}
                  className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]"
                >
                  <h3 className="text-sm font-semibold text-[var(--primary)] uppercase tracking-wide mb-2">
                    {label}
                  </h3>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {paper.structured_breakdown![key]}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="mb-8 flex items-center gap-4">
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="px-5 py-2.5 bg-[var(--primary)] hover:bg-[var(--primary-hover)] disabled:opacity-50 text-white rounded-lg font-medium transition-colors text-sm"
            >
              {analyzing ? "Analyzing..." : "Analyze Paper"}
            </button>
            {analyzing && (
              <span className="text-sm text-[var(--muted)]">
                Generating structured breakdown...
              </span>
            )}
            {analyzeError && (
              <span className="text-sm text-red-500">{analyzeError}</span>
            )}
          </div>
        )}
      </div>
      <div className="flex">
        <div className={`${chatOpen ? "w-[60%]" : "w-full max-w-5xl mx-auto"} px-8 pb-8`}>
          <div className="flex gap-6">
            <nav className="w-56 shrink-0 sticky top-8 self-start">
              <h3 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-3">
                Sections
              </h3>
              <ul className="space-y-1">
                {paper.sections.map((section) => (
                  <li key={section.id}>
                    <button
                      onClick={() => scrollToSection(section.id)}
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

        {chatOpen && (
          <div className="w-[40%] border-l border-[var(--border)] sticky top-0 h-screen flex flex-col bg-[var(--background)]">
            <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
              <h3 className="font-semibold text-sm">Ask about this paper</h3>
              {chatMessages.length > 0 && (
                <button
                  onClick={handleClearChat}
                  className="text-xs text-[var(--muted)] hover:text-red-400 transition-colors"
                >
                  Clear
                </button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {chatMessages.length === 0 && !chatLoading && (
                <div className="text-center text-[var(--muted)] text-sm mt-8">
                  <p className="mb-2">Ask a question about this paper.</p>
                  <p className="text-xs">
                    Answers are grounded in the paper&apos;s sections with citations.
                  </p>
                </div>
              )}

              {chatMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-xl px-4 py-3 text-sm ${
                      msg.role === "user"
                        ? "bg-[var(--primary)] text-white"
                        : "bg-[var(--card)] border border-[var(--border)]"
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>

                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-[var(--border)]/50 space-y-2">
                        <p className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide">
                          Sources
                        </p>
                        {msg.citations.map((cite, i) => (
                          <button
                            key={i}
                            onClick={() => {
                              if (cite.section_id) scrollToSection(cite.section_id);
                            }}
                            className="block w-full text-left text-xs p-2 rounded-lg bg-[var(--background)] hover:bg-[var(--primary)]/5 transition-colors"
                          >
                            <span className="font-medium text-[var(--primary)]">
                              {cite.section_title}
                            </span>
                            {cite.excerpt && (
                              <span className="block text-[var(--muted)] mt-0.5 line-clamp-2">
                                &ldquo;{cite.excerpt}&rdquo;
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl px-4 py-3">
                    <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
                      <div className="w-4 h-4 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
                      Thinking...
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-[var(--border)]">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleChatSend();
                    }
                  }}
                  placeholder="Ask a question..."
                  disabled={chatLoading}
                  className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--card)] text-sm focus:outline-none focus:border-[var(--primary)] disabled:opacity-50 placeholder:text-[var(--muted)]"
                />
                <button
                  onClick={handleChatSend}
                  disabled={chatLoading || !chatInput.trim()}
                  className="px-4 py-2.5 bg-[var(--primary)] hover:bg-[var(--primary-hover)] disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
