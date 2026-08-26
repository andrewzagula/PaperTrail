"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import {
  Blank,
  Body,
  Button,
  Empty,
  Item,
  Notice,
  Num,
  PageSkeleton,
  Panel,
  PanelHead,
  Score,
  Section,
  SectionHead,
  StatusPill,
  TopBar,
  WarnPanel,
  Working,
  toneFor,
} from "@/components";
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
    failed_stage?: string;
  } | null;
  warnings: string[];
  error_message: string | null;
  created_at: string;
  results: DiscoveryResult[];
}

const FAILED_STAGE_LABELS: Record<string, string> = {
  generating_queries: "while generating search queries",
  searching_arxiv: "while searching arXiv",
  ranking_results: "while ranking the results",
};

type IngestStatus = "loading" | "done" | "error";
type IngestingState = Record<string, { status: IngestStatus; message?: string }>;

export default function DiscoverResultsPage() {
  const params = useParams();
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
      const res = await fetch(`${API_URL}/discover/${runId}/ingest/${resultId}`, {
        method: "POST",
      });
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
            r.id === resultId ? { ...r, paper_id: data.paper_id } : r,
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
      <>
        <TopBar crumb={<b>Discovery run</b>} />
        <Body>
          <PageSkeleton />
        </Body>
      </>
    );
  }

  if (loadError && !run) {
    return (
      <>
        <TopBar crumb={<b>Discovery run</b>} />
        <Body>
          <Blank
            kind="Cannot open"
            title="That discovery run could not be loaded"
            actions={
              <>
                <Button onClick={handleRetryLoad}>Try again</Button>
                <Link href="/" className="btn ghost">
                  Back to Discover
                </Link>
              </>
            }
          >
            {loadError}
          </Blank>
        </Body>
      </>
    );
  }

  if (!run) {
    return (
      <>
        <TopBar crumb={<b>Discovery run</b>} />
        <Body>
          <Blank kind="Not here" title="That discovery run does not exist" />
        </Body>
      </>
    );
  }

  const isRunning = run.status === "pending" || run.status === "running";
  const budget = run.budget_used;
  const queries = run.generated_queries ?? [];

  return (
    <>
      <TopBar
        crumb={
          <>
            <Link href="/" className="lnk">
              Discover
            </Link>{" "}
            <span aria-hidden>/</span> <b>Run {run.id.slice(0, 4)}</b>
          </>
        }
        end={<StatusPill tone={toneFor(run.status)}>{run.status}</StatusPill>}
      />
      <Body>
        <h1 className="page-title" style={{ maxWidth: "60ch" }}>
          {run.question}
        </h1>
        <p className="page-sub">
          <Num>
            {run.results.length} result{run.results.length === 1 ? "" : "s"}
            {queries.length > 0
              ? ` from ${queries.length} quer${queries.length === 1 ? "y" : "ies"}`
              : ""}
            {budget?.total_papers_fetched != null
              ? ` · ${budget.total_papers_fetched} fetched, ${budget.papers_ranked ?? 0} ranked`
              : ""}
          </Num>
        </p>

        {loadError ? (
          <Section>
            <WarnPanel title="The last refresh failed">
              {loadError} The results below may be out of date.
            </WarnPanel>
            <div style={{ marginTop: "var(--space-lg)" }}>
              <Button variant="ghost" size="sm" onClick={handleRetryLoad}>
                Refresh
              </Button>
            </div>
          </Section>
        ) : null}

        {isRunning ? (
          <Section>
            <Working>
              {run.status === "pending"
                ? "Starting. Queries first, then arXiv, then ranking."
                : "Searching arXiv and ranking what comes back."}
            </Working>
          </Section>
        ) : null}

        {run.status === "failed" ? (
          <Section>
            <WarnPanel
              title={`This run stopped${
                run.budget_used?.failed_stage &&
                FAILED_STAGE_LABELS[run.budget_used.failed_stage]
                  ? ` ${FAILED_STAGE_LABELS[run.budget_used.failed_stage]}`
                  : ""
              }`}
            >
              {run.error_message || "No reason was recorded."}
              {queries.length > 0
                ? " The queries below were generated before it stopped, so you can see how far it got."
                : ""}
            </WarnPanel>
          </Section>
        ) : null}

        {queries.length > 0 ? (
          <Section className="col-narrow">
            <Panel>
              <PanelHead
                end={
                  <button
                    type="button"
                    className="lnk"
                    onClick={() => setShowQueries((current) => !current)}
                    style={{ background: "none", border: 0, font: "inherit" }}
                  >
                    {showQueries ? "Hide" : "Show"}
                  </button>
                }
              >
                Generated queries
              </PanelHead>
              {showQueries
                ? queries.map((query, index) => (
                    <div key={index} className="row mono">
                      <span>
                        {index + 1}. {query}
                      </span>
                    </div>
                  ))
                : null}
            </Panel>
          </Section>
        ) : null}

        {run.warnings.length > 0 ? (
          <Section className="col-narrow">
            <WarnPanel title="Coverage notes">
              {run.warnings.join(" ")} These are relevance-ranked arXiv matches,
              not an exhaustive review of the literature.
            </WarnPanel>
          </Section>
        ) : null}

        <Section className="col-narrow">
          <SectionHead>
            {run.results.length === 0
              ? "Results"
              : `${run.results.length} result${run.results.length === 1 ? "" : "s"}`}
          </SectionHead>

          {run.results.length === 0 ? (
            run.status === "complete" ? (
              <Empty>
                Nothing came back for this question. A narrower or differently
                worded question usually helps.
              </Empty>
            ) : (
              <Empty>No results yet.</Empty>
            )
          ) : (
            run.results.map((result) => {
              const state = ingesting[result.id];
              const score =
                result.relevance_score !== null
                  ? `${(result.relevance_score * 100).toFixed(0)}% relevant`
                  : null;

              return (
                <Item
                  key={result.id}
                  index={String(result.rank_order).padStart(2, "0")}
                >
                  {score ? (
                    <div className="toprow">
                      <Score weak={(result.relevance_score ?? 0) < 0.7}>
                        {score}
                      </Score>
                    </div>
                  ) : null}
                  <h3>{result.title}</h3>
                  {result.authors ? <p className="auth">{result.authors}</p> : null}
                  {result.relevance_reason ? (
                    <p className="why">{result.relevance_reason}</p>
                  ) : null}
                  {result.abstract ? <p className="abs">{result.abstract}</p> : null}
                  <div className="foot">
                    {result.published ? <Num>{result.published}</Num> : null}
                    <Num>
                      <a
                        href={`https://arxiv.org/abs/${result.arxiv_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="lnk"
                      >
                        arXiv:{result.arxiv_id}
                      </a>
                    </Num>
                    <span style={{ marginLeft: "auto" }}>
                      {result.paper_id ? (
                        <Link
                          href={`/papers/${result.paper_id}`}
                          className="btn soft sm"
                        >
                          View in library
                        </Link>
                      ) : state?.status === "loading" ? (
                        <Working>Adding</Working>
                      ) : (
                        <Button
                          size="sm"
                          variant={state?.status === "error" ? "ghost" : "primary"}
                          onClick={() => handleIngest(result.id)}
                        >
                          {state?.status === "error" ? "Try again" : "Add to library"}
                        </Button>
                      )}
                    </span>
                  </div>
                  {state?.status === "error" ? (
                    <div className="fixline">
                      <Notice tone="bad">
                        {state.message || "Failed to add this paper."}
                      </Notice>
                    </div>
                  ) : null}
                </Item>
              );
            })
          )}
        </Section>
      </Body>
    </>
  );
}
