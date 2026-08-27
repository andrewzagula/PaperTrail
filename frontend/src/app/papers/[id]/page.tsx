"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

import {
  Blank,
  Button,
  Cite,
  Empty,
  Input,
  Notice,
  Num,
  Panel,
  PanelHead,
  Provenance,
  Row,
  Section,
  SectionHead,
  Spinner,
  Working,
} from "@/components";
import { cx } from "@/lib/cx";
import { getApiErrorMessage } from "@/lib/api-errors";

import { Breakdown, usePaper } from "./paper-context";

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

const BREAKDOWN_FIELDS: { key: keyof Breakdown; label: string }[] = [
  { key: "problem", label: "Problem" },
  { key: "method", label: "Method" },
  { key: "key_contributions", label: "Key contributions" },
  { key: "results", label: "Results" },
  { key: "limitations", label: "Limitations" },
  { key: "future_work", label: "Future work" },
];

/* The three panels that share the paper's own URL. The paper, the header
   above, and the tab strip all belong to the layout. */
export default function PaperPanels() {
  const params = useParams();
  const paperId = params.id as string;
  const { paper, setPaper, tab, setTab } = usePaper();

  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistoryLoaded, setChatHistoryLoaded] = useState(false);
  const [pdfAvailable, setPdfAvailable] = useState<boolean | null>(null);

  const chatEndRef = useRef<HTMLDivElement | null>(null);

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
    if (tab !== "paper" || pdfAvailable !== null) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_URL}/papers/${paperId}/pdf`, {
          method: "HEAD",
        });
        if (!cancelled) setPdfAvailable(res.ok);
      } catch {
        if (!cancelled) setPdfAvailable(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [tab, pdfAvailable, paperId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [chatMessages, chatLoading]);

  const handleAnalyze = async () => {
    if (analyzing) return;
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

  const breakdown = paper.structured_breakdown;

  return (
    <>
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
                  {section.content
                    .split("\n\n")
                    .filter((para) => para.trim())
                    .map((para, index) => (
                      <p key={index}>{para}</p>
                    ))}
                </div>
              ))}
            </div>
          </>
        )
      ) : tab === "paper" ? (
        pdfAvailable === false ? (
          <Empty>
            This paper has no PDF stored on disk, so the original cannot be
            shown. The extracted text is still available under Sections.
          </Empty>
        ) : (
          <div className="pdf-frame">
            <iframe
              src={`${API_URL}/papers/${paperId}/pdf`}
              title={`${paper.title} (PDF)`}
            />
          </div>
        )
      ) : null}
    </>
  );
}
