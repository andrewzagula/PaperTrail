"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  Body,
  Button,
  Empty,
  Input,
  Notice,
  Num,
  PageHeader,
  Panel,
  PanelHead,
  Row,
  Section,
  Split,
  StatusPill,
  TopBar,
  toneFor,
} from "@/components";
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

function relativeDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  const minutes = Math.round((Date.now() - parsed.getTime()) / 60000);
  if (minutes < 2) return "just now";
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
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
    <>
      <TopBar
        crumb={<b>Discover</b>}
        end={
          loaded ? (
            <Num>
              {runs.length} run{runs.length === 1 ? "" : "s"} &middot;{" "}
              {papers.length} paper{papers.length === 1 ? "" : "s"}
            </Num>
          ) : undefined
        }
      />
      <Body>
        <PageHeader
          title="Start with a research question"
          sub="Discover, understand, compare, and turn papers into ideas. Everything stays on this machine."
        />

        <div className="askrow">
          <Input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !submitting) {
                handleDiscover();
              }
            }}
            placeholder="What is your research question?"
            disabled={submitting}
            aria-label="Research question"
          />
          <Button onClick={handleDiscover} disabled={submitting || !question.trim()}>
            {submitting ? "Starting" : "Discover"}
          </Button>
        </div>

        {error ? (
          <div style={{ marginTop: "var(--space-lg)" }}>
            <Notice tone="bad">{error}</Notice>
          </div>
        ) : null}

        <Section>
          <Split>
            <Panel>
              <PanelHead
                end={
                  <Link href="/library" className="lnk">
                    All runs
                  </Link>
                }
              >
                Recent discoveries
              </PanelHead>
              {!loaded ? (
                <Row>Loading</Row>
              ) : runs.length === 0 ? (
                <div className="row">
                  <span className="sub">
                    Nothing yet. Ask a question above to start one.
                  </span>
                </div>
              ) : (
                runs.slice(0, 6).map((run) => (
                  <Row
                    key={run.id}
                    href={`/discover/${run.id}`}
                    end={
                      <>
                        {run.status === "complete" ? (
                          <Num>{run.num_results} results</Num>
                        ) : null}
                        <StatusPill tone={toneFor(run.status)}>
                          {run.status}
                        </StatusPill>
                      </>
                    }
                  >
                    {run.question}
                    <span className="sub">{relativeDate(run.created_at)}</span>
                  </Row>
                ))
              )}
            </Panel>

            <Panel>
              <PanelHead
                end={
                  <Link href="/papers/new" className="lnk">
                    Add paper
                  </Link>
                }
              >
                Library
              </PanelHead>
              {!loaded ? (
                <Row>Loading</Row>
              ) : papers.length === 0 ? (
                <div className="row">
                  <span className="sub">
                    No papers yet. Add one, or take one from a discovery run.
                  </span>
                </div>
              ) : (
                papers.slice(0, 6).map((paper) => (
                  <Row
                    key={paper.id}
                    href={`/papers/${paper.id}`}
                    end={<Num>{relativeDate(paper.created_at)}</Num>}
                  >
                    {paper.title}
                    {paper.authors ? (
                      <span className="sub">{paper.authors}</span>
                    ) : null}
                  </Row>
                ))
              )}
            </Panel>
          </Split>
        </Section>
      </Body>
    </>
  );
}
