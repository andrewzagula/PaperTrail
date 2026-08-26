"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import {
  Blank,
  Body,
  Button,
  Cite,
  Empty,
  Input,
  Notice,
  Num,
  PageSkeleton,
  Panel,
  PanelHead,
  Provenance,
  Row,
  Section,
  SectionHead,
  Spinner,
  StatusPill,
  TopBar,
  Working,
} from "@/components";
import { cx } from "@/lib/cx";
import { addPaperToCompare } from "@/lib/compare-selection";
import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Citation {
  section_title: string;
  excerpt: string;
  section_id?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

interface Section_ {
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
  sections: Section_[];
}

type TabKey = "breakdown" | "chat" | "sections";

const BREAKDOWN_FIELDS: { key: keyof Breakdown; label: string }[] = [
  { key: "problem", label: "Problem" },
  { key: "method", label: "Method" },
  { key: "key_contributions", label: "Key contributions" },
  { key: "results", label: "Results" },
  { key: "limitations", label: "Limitations" },
  { key: "future_work", label: "Future work" },
];

const TABS: { value: TabKey; label: string }[] = [
  { value: "breakdown", label: "Breakdown" },
  { value: "chat", label: "Chat" },
  { value: "sections", label: "Sections" },
];

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "an unknown date";
  }
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** arXiv ids are a fact worth showing plainly, not a URL to decode. */
function arxivId(url: string | null): string | null {
  if (!url) {
    return null;
  }
  const match = url.match(/(\d{4}\.\d{4,5}(v\d+)?)/);
  return match ? `arXiv:${match[1]}` : null;
}

export default function PaperView() {
  const params = useParams();
  const router = useRouter();
  const paperId = params.id as string;

  const [paper, setPaper] = useState<Paper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<TabKey>("breakdown");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistoryLoaded, setChatHistoryLoaded] = useState(false);
  const [compareNotice, setCompareNotice] = useState<{
    tone: "quiet" | "bad";
    message: string;
  } | null>(null);

  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    async function fetchPaper() {
      try {
        const res = await fetch(`${API_URL}/papers/${paperId}`);
        if (!res.ok) {
          throw new Error(await getApiErrorMessage(res, "Paper not found"));
        }
        const data = await res.json();
        setPaper(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load paper");
      } finally {
        setLoading(false);
      }
    }

    fetchPaper();
  }, [paperId]);

  useEffect(() => {
    if (tab !== "chat" || chatHistoryLoaded) {
      return;
    }
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
  }, [tab, chatHistoryLoaded, paperId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [chatMessages, chatLoading]);

  const handleAnalyze = async () => {
    if (!paper || analyzing) return;
    setAnalyzing(true);
    setAnalyzeError("");
    try {
      const res = await fetch(`${API_URL}/papers/${paperId}/analyze`, {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Analysis failed"));
      }
      const breakdown = await res.json();
      setPaper({ ...paper, structured_breakdown: breakdown });
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAddToCompare = () => {
    if (!paper) return;

    const result = addPaperToCompare(paper.id);

    if (result.added) {
      setCompareNotice({
        tone: "quiet",
        message:
          result.ids.length >= 2
            ? `Added. ${result.ids.length} papers are ready to compare.`
            : "Added. One more paper and you can run a comparison.",
      });
      return;
    }

    if (result.reason === "duplicate") {
      setCompareNotice({
        tone: "quiet",
        message: "This paper is already on the compare list.",
      });
      return;
    }

    setCompareNotice({
      tone: "bad",
      message:
        "The compare list already holds five papers. Open Compare to change the selection.",
    });
  };

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
        throw new Error(await getApiErrorMessage(res, "Chat failed"));
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

  const goToSection = (sectionId: string) => {
    setTab("sections");
    window.setTimeout(() => {
      document
        .getElementById(`section-${sectionId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  };

  if (loading) {
    return (
      <>
        <TopBar crumb={<b>Paper</b>} />
        <Body>
          <PageSkeleton />
        </Body>
      </>
    );
  }

  if (error || !paper) {
    return (
      <>
        <TopBar crumb={<b>Paper</b>} />
        <Body>
          <Blank
            kind="Cannot open"
            title="That paper is not here"
            actions={
              <Link href="/library" className="btn ghost">
                Back to library
              </Link>
            }
          >
            {error || "Paper not found."}
          </Blank>
        </Body>
      </>
    );
  }

  const breakdown = paper.structured_breakdown;
  const arxiv = arxivId(paper.arxiv_url);

  return (
    <>
      <TopBar
        crumb={
          <>
            <Link href="/library" className="lnk">
              Library
            </Link>{" "}
            <span aria-hidden>/</span> <b>{paper.title}</b>
          </>
        }
      />
      <Body>
        <div className="paper-head">
          <div>
            <h1 className="page-title" style={{ maxWidth: "44ch" }}>
              {paper.title}
            </h1>
            {paper.authors ? (
              <p className="page-sub">
                {paper.authors}
                {arxiv ? <Num> {arxiv}</Num> : null}
              </p>
            ) : null}
          </div>
          <div className="paper-acts">
            <Button onClick={() => router.push(`/ideas?paper=${encodeURIComponent(paper.id)}`)}>
              Generate ideas
            </Button>
            <Button variant="ghost" onClick={handleAddToCompare}>
              Add to comparison
            </Button>
          </div>
        </div>

        <dl className="paper-meta">
          <div>
            <dt>Added</dt>
            <dd>
              <Num>{formatDate(paper.created_at)}</Num>
            </dd>
          </div>
          <div>
            <dt>Sections</dt>
            <dd>
              <Num>{paper.sections.length}</Num>
            </dd>
          </div>
          <div>
            <dt>Breakdown</dt>
            <dd>
              <StatusPill tone={breakdown ? "ok" : "idle"}>
                {breakdown ? "ready" : "not generated"}
              </StatusPill>
            </dd>
          </div>
          {paper.arxiv_url ? (
            <div>
              <dt>Source</dt>
              <dd>
                <a
                  href={paper.arxiv_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="lnk"
                >
                  arXiv
                </a>
              </dd>
            </div>
          ) : null}
        </dl>

        {compareNotice ? (
          <div style={{ marginTop: "var(--space-lg)" }}>
            <Notice tone={compareNotice.tone}>{compareNotice.message}</Notice>
          </div>
        ) : null}

        {/* Three panels plus one destination. Implement is a link, not a
            panel, because it opens a page of its own. */}
        <div className="tabs" style={{ marginTop: "var(--space-3xl)" }}>
          {TABS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={cx("tab", tab === item.value && "on")}
              aria-current={tab === item.value ? "true" : undefined}
              onClick={() => setTab(item.value)}
            >
              {item.label}
            </button>
          ))}
          <Link href={`/papers/${paper.id}/implement`} className="tab">
            Implement
            <StatusPill tone="idle">plan</StatusPill>
          </Link>
        </div>

        {tab === "breakdown" ? (
          breakdown ? (
            <div className="reading">
              <Provenance>
                Generated from the paper&apos;s own text. The abstract below it is
                the paper&apos;s own words, unchanged.
              </Provenance>
              {BREAKDOWN_FIELDS.map(({ key, label }) => (
                <div key={key} className="bd-sec">
                  <h3>{label}</h3>
                  <p>{breakdown[key]}</p>
                </div>
              ))}
              {paper.abstract ? (
                <div className="bd-sec">
                  <h3>Abstract</h3>
                  <p>{paper.abstract}</p>
                  <Cite>The paper&apos;s own words</Cite>
                </div>
              ) : null}
            </div>
          ) : (
            <Section>
              <Blank
                kind="Nothing generated yet"
                quiet
                title="No breakdown for this paper yet"
                actions={
                  <Button onClick={handleAnalyze} disabled={analyzing}>
                    {analyzing ? "Reading the paper" : "Generate breakdown"}
                  </Button>
                }
              >
                A breakdown restates the paper in six fields: problem, method,
                contributions, results, limitations, and future work. It takes a
                minute and only happens when you ask.
              </Blank>
              {paper.abstract ? (
                <div className="reading">
                  <div className="bd-sec">
                    <h3>Abstract</h3>
                    <p>{paper.abstract}</p>
                    <Cite>The paper&apos;s own words</Cite>
                  </div>
                </div>
              ) : null}
              {analyzing ? (
                <div style={{ marginTop: "var(--space-xl)" }}>
                  <Working>Reading the paper and drafting the six fields</Working>
                </div>
              ) : null}
              {analyzeError ? (
                <div style={{ marginTop: "var(--space-xl)" }}>
                  <Notice tone="bad">{analyzeError}</Notice>
                </div>
              ) : null}
            </Section>
          )
        ) : null}

        {tab === "chat" ? (
          <Section>
            <SectionHead
              end={
                chatMessages.length > 0 ? (
                  <Button variant="ghost" size="sm" onClick={handleClearChat}>
                    Clear
                  </Button>
                ) : undefined
              }
            >
              Ask about this paper
            </SectionHead>
            <Provenance>
              Answers are drawn from this paper&apos;s sections and cite them. If
              the paper does not say, the answer says so.
            </Provenance>

            {chatMessages.length === 0 && !chatLoading ? (
              <Empty>
                Nothing asked yet. Try what the evaluation setup was, or what the
                paper does not cover.
              </Empty>
            ) : (
              <div className="chat">
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={cx("msg", msg.role === "user" && "you")}
                  >
                    <p>{msg.content}</p>
                    {msg.citations && msg.citations.length > 0 ? (
                      <div className="srcs">
                        {msg.citations.map((cite, i) =>
                          cite.section_id ? (
                            <button
                              key={i}
                              type="button"
                              className="cite"
                              onClick={() => goToSection(cite.section_id!)}
                            >
                              {cite.section_title}
                            </button>
                          ) : (
                            <Cite key={i}>{cite.section_title}</Cite>
                          ),
                        )}
                      </div>
                    ) : null}
                  </div>
                ))}
                {chatLoading ? (
                  <div className="msg">
                    <Working>Reading the sections</Working>
                  </div>
                ) : null}
                <div ref={chatEndRef} />
              </div>
            )}

            <div className="chat-form">
              <Input
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    handleChatSend();
                  }
                }}
                placeholder="Ask a question about this paper"
                disabled={chatLoading}
                aria-label="Ask a question about this paper"
              />
              <Button
                onClick={handleChatSend}
                disabled={chatLoading || !chatInput.trim()}
              >
                {chatLoading ? <Spinner /> : "Send"}
              </Button>
            </div>
          </Section>
        ) : null}

        {tab === "sections" ? (
          paper.sections.length === 0 ? (
            <Section>
              <Empty>
                No sections were extracted from this paper, so chat and breakdown
                have nothing to draw on.
              </Empty>
            </Section>
          ) : (
            <>
              <Section>
                <Panel>
                  <PanelHead end={<Num>{paper.sections.length}</Num>}>
                    Jump to
                  </PanelHead>
                  {paper.sections.map((section) => (
                    <Row
                      key={section.id}
                      onClick={() => goToSection(section.id)}
                      end={<Num>{section.section_order}</Num>}
                    >
                      {section.section_title}
                    </Row>
                  ))}
                </Panel>
              </Section>

              <div className="reading">
                {paper.sections.map((section) => (
                  <div
                    key={section.id}
                    id={`section-${section.id}`}
                    className="bd-sec"
                  >
                    <h3>{section.section_title}</h3>
                    <p>{section.content}</p>
                  </div>
                ))}
              </div>
            </>
          )
        ) : null}
      </Body>
    </>
  );
}
