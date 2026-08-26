"use client";

import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSelectedLayoutSegment } from "next/navigation";

import {
  Blank,
  Body,
  Button,
  Notice,
  Num,
  PageSkeleton,
  StatusPill,
  TopBar,
  WarnPanel,
  Working,
  toneFor,
} from "@/components";
import { cx } from "@/lib/cx";
import { addPaperToCompare } from "@/lib/compare-selection";
import { getApiErrorMessage } from "@/lib/api-errors";
import { explainEmbedding, needsEmbedding } from "@/lib/embedding";

import { Paper, PaperProvider, TabKey } from "./paper-context";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

/* ------------------------------------------------------------------
   Everything above the tab strip belongs to the paper, not to any one
   panel, so it lives here and stays mounted while you move between
   them. The plan keeps its own URL because a generated plan is worth
   linking to; it just stops behaving like a different place.
   ------------------------------------------------------------------ */

export default function PaperLayout({ children }: { children: ReactNode }) {
  const params = useParams();
  const router = useRouter();
  const paperId = params.id as string;

  /* null on /papers/[id], "implement" one level down. Read as a segment
     rather than matched against the pathname, so another child route
     later needs no new string handling. */
  const segment = useSelectedLayoutSegment();
  const onPlan = segment === "implement";

  const [paper, setPaper] = useState<Paper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<TabKey>("breakdown");
  const [compareNotice, setCompareNotice] = useState<{
    tone: "quiet" | "bad";
    message: string;
  } | null>(null);
  const [reembedding, setReembedding] = useState(false);
  const [reembedError, setReembedError] = useState("");

  useEffect(() => {
    async function fetchPaper() {
      try {
        const res = await fetch(`${API_URL}/papers/${paperId}`);
        if (!res.ok) {
          throw new Error(await getApiErrorMessage(res, "Paper not found"));
        }
        setPaper(await res.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load paper");
      } finally {
        setLoading(false);
      }
    }

    fetchPaper();
  }, [paperId]);

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

  /* Re-embedding is offered here as well as in Library, because this is
     where a person notices the paper is out of step: they open it to chat
     with it and the answers stop lining up. */
  const handleReembed = async () => {
    if (!paper) return;

    setReembedding(true);
    setReembedError("");

    try {
      const res = await fetch(`${API_URL}/papers/${paper.id}/reembed`, {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Failed to re-embed."));
      }

      const data: {
        embedding_status: string;
        embedding_provider: string;
        embedding_model: string;
        embedded_at: string | null;
      } = await res.json();

      setPaper({ ...paper, ...data });
    } catch (err) {
      setReembedError(err instanceof Error ? err.message : "Failed to re-embed.");
    } finally {
      setReembedding(false);
    }
  };

  /* From the plan, a panel tab has to navigate as well as switch. From the
     panels it only switches, which is why these are buttons and Implement
     is a link: each one does what it looks like it does. */
  const openPanel = (next: TabKey) => {
    setTab(next);
    if (onPlan) {
      router.push(`/papers/${paperId}`);
    }
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
            <Button
              onClick={() =>
                router.push(`/ideas?paper=${encodeURIComponent(paper.id)}`)
              }
            >
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
          <div>
            <dt>Embedding</dt>
            <dd>
              <StatusPill tone={toneFor(paper.embedding_status)}>
                {paper.embedding_status}
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

        {needsEmbedding(paper.embedding_status) ? (
          <div style={{ marginTop: "var(--space-2xl)" }}>
            <WarnPanel
              title="This paper is not embedded with the model you have set"
              actions={
                reembedding ? (
                  <Working>Sending the sections to the embedding provider</Working>
                ) : (
                  <Button size="sm" onClick={handleReembed}>
                    Re-embed it
                  </Button>
                )
              }
            >
              {explainEmbedding(paper.embedding_status)} Chat answers and
              comparisons that draw on this paper can disagree with the rest of
              your library until it is re-embedded. The model set now is{" "}
              {paper.embedding_provider} / {paper.embedding_model}.
            </WarnPanel>
            {reembedError ? (
              <div style={{ marginTop: "var(--space-lg)" }}>
                <Notice tone="bad">{reembedError}</Notice>
              </div>
            ) : null}
          </div>
        ) : null}

        {compareNotice ? (
          <div style={{ marginTop: "var(--space-lg)" }}>
            <Notice tone={compareNotice.tone}>{compareNotice.message}</Notice>
          </div>
        ) : null}

        <div className="tabs" style={{ marginTop: "var(--space-3xl)" }}>
          {TABS.map((item) => {
            const on = !onPlan && tab === item.value;
            return (
              <button
                key={item.value}
                type="button"
                className={cx("tab", on && "on")}
                aria-current={on ? "true" : undefined}
                onClick={() => openPanel(item.value)}
              >
                {item.label}
              </button>
            );
          })}
          <Link
            href={`/papers/${paper.id}/implement`}
            className={cx("tab", onPlan && "on")}
            aria-current={onPlan ? "page" : undefined}
          >
            Implement
            <StatusPill tone="idle">plan</StatusPill>
          </Link>
        </div>

        <PaperProvider value={{ paper, setPaper, tab, setTab }}>
          {children}
        </PaperProvider>
      </Body>
    </>
  );
}
