"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import {
  Body,
  Button,
  Checkbox,
  Chip,
  ChipRow,
  Empty,
  Fact,
  Facts,
  Field,
  Input,
  Item,
  Notice,
  Num,
  PageHeader,
  PageSkeleton,
  PlainList,
  Provenance,
  Section,
  SectionHead,
  SelectionBar,
  Tag,
  TopBar,
  WarnPanel,
  Working,
} from "@/components";
import type { TagTone } from "@/components";
import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_IDEA_SELECTION = 5;

interface PaperListItem {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
  has_structured_breakdown?: boolean;
}

interface SelectedIdeaPaperResponse {
  id: string;
  title: string;
  authors: string | null;
  arxiv_url: string | null;
  created_at: string;
}

type TransformationType = "combine" | "ablate" | "extend" | "apply";
type Feasibility = "low" | "medium" | "high";

interface IdeaResponse {
  title: string;
  transformation_type: TransformationType;
  description: string;
  why_interesting: string;
  feasibility: Feasibility;
  evidence_basis: string[];
  risks_or_unknowns: string[];
  warnings: string[];
}

interface IdeaGenerationResponse {
  selected_papers: SelectedIdeaPaperResponse[];
  source_topic: string | null;
  ideas: IdeaResponse[];
  warnings: string[];
}

interface SaveIdeasResponse {
  id: string;
  title: string;
  item_type: "idea";
  paper_ids: string[];
  created_at: string;
}

const TRANSFORMATION_LABELS: Record<TransformationType, string> = {
  combine: "Combine",
  ablate: "Ablate",
  extend: "Extend",
  apply: "Apply",
};

/* Feasibility runs the opposite way from severity: the low one is the
   one worth flagging, so the alarm grade goes to "low". */
const FEASIBILITY_TONES: Record<Feasibility, TagTone> = {
  low: "high",
  medium: "med",
  high: "default",
};

function formatDate(value: string): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return "an unknown date";
  }

  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function normalizeQueryPaperIds(values: string[]): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();

  for (const value of values) {
    const id = value.trim();
    if (!id || seen.has(id)) {
      continue;
    }

    seen.add(id);
    ids.push(id);
    if (ids.length >= MAX_IDEA_SELECTION) {
      break;
    }
  }

  return ids;
}

function createSourceSignature(paperIds: string[], topic: string): string {
  return `${paperIds.join(",")}::${topic.trim()}`;
}

function createSaveKey(result: IdeaGenerationResponse, title: string): string {
  const paperIds = result.selected_papers.map((paper) => paper.id).join(",");
  return `${paperIds}::${result.source_topic || ""}::${title}`;
}

function createDefaultIdeasTitle(result: IdeaGenerationResponse): string {
  const topic = result.source_topic?.trim();
  const [firstPaper, ...remainingPapers] = result.selected_papers;

  if (!firstPaper && topic) {
    return `Ideas: ${topic}`;
  }

  if (!firstPaper) {
    return "Ideas";
  }

  if (remainingPapers.length === 0) {
    return `Ideas: ${firstPaper.title}`;
  }

  return `Ideas: ${firstPaper.title} (+${remainingPapers.length} more)`;
}

function IdeaEntry({ idea, index }: { idea: IdeaResponse; index: number }) {
  return (
    <Item index={index + 1}>
      <h3>{idea.title}</h3>
      <div className="foot">
        <Tag>{TRANSFORMATION_LABELS[idea.transformation_type]}</Tag>
        <Tag tone={FEASIBILITY_TONES[idea.feasibility]}>
          {idea.feasibility} feasibility
        </Tag>
      </div>
      <div style={{ marginTop: "var(--space-xl)" }}>
        <Facts>
          <Fact k="What it is">{idea.description}</Fact>
          <Fact k="Why it is interesting">{idea.why_interesting}</Fact>
          <Fact k="Grounded in" none="Nothing was cited.">
            {idea.evidence_basis.length > 0 ? (
              <PlainList items={idea.evidence_basis} />
            ) : null}
          </Fact>
          <Fact k="Risks and unknowns" none="None returned.">
            {idea.risks_or_unknowns.length > 0 ? (
              <PlainList items={idea.risks_or_unknowns} />
            ) : null}
          </Fact>
          {idea.warnings.length > 0 ? (
            <Fact k="Warnings">
              <PlainList items={idea.warnings} />
            </Fact>
          ) : null}
        </Facts>
      </div>
    </Item>
  );
}

function IdeasPageContent() {
  const searchParams = useSearchParams();

  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(true);
  const [libraryError, setLibraryError] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectionMessage, setSelectionMessage] = useState("");
  const [topic, setTopic] = useState("");
  const [ideaResult, setIdeaResult] = useState<IdeaGenerationResponse | null>(null);
  const [resultSourceSignature, setResultSourceSignature] = useState("");
  const [generationLoading, setGenerationLoading] = useState(false);
  const [generationError, setGenerationError] = useState("");
  const [saveTitle, setSaveTitle] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState("");
  const [lastSavedKey, setLastSavedKey] = useState("");

  useEffect(() => {
    const queryPaperIds = searchParams.getAll("paper");
    const normalizedIds = normalizeQueryPaperIds(queryPaperIds);
    setSelectedIds(normalizedIds);

    if (queryPaperIds.length > MAX_IDEA_SELECTION) {
      setSelectionMessage(
        `That link named more than ${MAX_IDEA_SELECTION} papers. The first ${MAX_IDEA_SELECTION} are selected.`,
      );
    }
  }, [searchParams]);

  useEffect(() => {
    async function loadPapers() {
      setLibraryLoading(true);
      setLibraryError("");

      try {
        const res = await fetch(`${API_URL}/papers/`);
        if (!res.ok) {
          throw new Error(
            await getApiErrorMessage(res, "Failed to load your paper library."),
          );
        }

        const data: PaperListItem[] = await res.json();
        setPapers(data);
      } catch (err) {
        setLibraryError(
          err instanceof Error ? err.message : "Failed to load your paper library.",
        );
      } finally {
        setLibraryLoading(false);
      }
    }

    loadPapers();
  }, []);

  useEffect(() => {
    if (libraryLoading) {
      return;
    }

    const availableIds = new Set(papers.map((paper) => paper.id));
    setSelectedIds((current) => current.filter((paperId) => availableIds.has(paperId)));
  }, [libraryLoading, papers]);

  const sourceSignature = createSourceSignature(selectedIds, topic);
  const hasSource = selectedIds.length > 0 || topic.trim().length > 0;
  const generationDisabled =
    generationLoading || !hasSource || (libraryLoading && selectedIds.length > 0);

  const clearGeneratedOutput = () => {
    setIdeaResult(null);
    setResultSourceSignature("");
    setGenerationError("");
    setSaveTitle("");
    setSaveLoading(false);
    setSaveError("");
    setSaveSuccess("");
    setLastSavedKey("");
  };

  const handleTopicChange = (value: string) => {
    setTopic(value);
    if (ideaResult || generationError || saveSuccess || saveError) {
      clearGeneratedOutput();
    }
  };

  const handleTogglePaper = (paperId: string) => {
    if (generationLoading) {
      return;
    }

    if (selectedIds.includes(paperId)) {
      setSelectedIds(selectedIds.filter((id) => id !== paperId));
      setSelectionMessage("");
      clearGeneratedOutput();
      return;
    }

    if (selectedIds.length >= MAX_IDEA_SELECTION) {
      setSelectionMessage(
        `Ideas draw on at most ${MAX_IDEA_SELECTION} papers. Deselect one to add another.`,
      );
      return;
    }

    setSelectedIds([...selectedIds, paperId]);
    setSelectionMessage("");
    clearGeneratedOutput();
  };

  const handleGenerateIdeas = async () => {
    if (generationLoading) {
      return;
    }

    const normalizedTopic = topic.trim();

    setGenerationError("");
    setSelectionMessage("");

    if (!selectedIds.length && !normalizedTopic) {
      setGenerationError("Select at least one paper, or type a topic to work from.");
      return;
    }

    setGenerationLoading(true);
    setSaveError("");
    setSaveSuccess("");

    try {
      const body: { paper_ids?: string[]; topic?: string } = {};
      if (selectedIds.length > 0) {
        body.paper_ids = selectedIds;
      }
      if (normalizedTopic) {
        body.topic = normalizedTopic;
      }

      const res = await fetch(`${API_URL}/papers/ideas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Idea generation failed."));
      }

      const data: IdeaGenerationResponse = await res.json();
      setIdeaResult(data);
      setResultSourceSignature(sourceSignature);
      setSaveTitle(createDefaultIdeasTitle(data));
      setSaveError("");
      setSaveSuccess("");
      setLastSavedKey("");
    } catch (err) {
      setIdeaResult(null);
      setResultSourceSignature("");
      setGenerationError(
        err instanceof Error ? err.message : "Idea generation failed.",
      );
    } finally {
      setGenerationLoading(false);
    }
  };

  const handleSaveIdeas = async () => {
    if (!ideaResult) {
      return;
    }

    const normalizedTitle = saveTitle.trim();
    if (!normalizedTitle) {
      setSaveError("Give this set a title before saving.");
      setSaveSuccess("");
      return;
    }

    const saveKey = createSaveKey(ideaResult, normalizedTitle);
    if (saveKey === lastSavedKey) {
      setSaveError("This set is already saved under that title.");
      setSaveSuccess("");
      return;
    }

    setSaveLoading(true);
    setSaveError("");
    setSaveSuccess("");

    try {
      const paperIds = ideaResult.selected_papers.map((paper) => paper.id);
      const res = await fetch(`${API_URL}/papers/ideas/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: normalizedTitle,
          paper_ids: paperIds,
          idea_result: ideaResult,
        }),
      });

      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Failed to save ideas."));
      }

      const data: SaveIdeasResponse = await res.json();
      setSaveTitle(data.title);
      setSaveSuccess(`Saved to your library as "${data.title}".`);
      setLastSavedKey(saveKey);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save ideas.");
    } finally {
      setSaveLoading(false);
    }
  };

  const resultIsStale =
    Boolean(ideaResult) && resultSourceSignature !== sourceSignature;
  const showResult = ideaResult && !resultIsStale;

  const crumbTail = selectedIds.length
    ? `from ${selectedIds.length} paper${selectedIds.length === 1 ? "" : "s"}`
    : topic.trim()
      ? "from a topic"
      : "no sources yet";

  return (
    <>
      <TopBar
        crumb={
          <>
            <b>Ideas</b> <span aria-hidden>/</span> {crumbTail}
          </>
        }
        end={
          showResult ? (
            <Button variant="ghost" size="sm" onClick={handleSaveIdeas} disabled={saveLoading}>
              {saveLoading ? "Saving" : "Save ideas"}
            </Button>
          ) : undefined
        }
      />
      <Body className="col-mid">
        <PageHeader
          title="Ideas"
          sub="Research directions built from papers you already have. Every idea names what it draws on."
        />

        <Section>
          <SectionHead>Sources</SectionHead>
          <Field label="Topic or focus, if you have one">
            <textarea
              className="input"
              value={topic}
              onChange={(event) => handleTopicChange(event.target.value)}
              placeholder="A research question, a domain, an evaluation angle"
              disabled={generationLoading}
              rows={3}
              style={{ resize: "vertical", lineHeight: "var(--leading-body)" }}
            />
          </Field>

          {selectionMessage ? (
            <div style={{ marginTop: "var(--space-lg)" }}>
              <Notice tone="quiet">{selectionMessage}</Notice>
            </div>
          ) : null}
        </Section>

        <Section>
          <SectionHead
            end={
              <Link href="/papers/new" className="lnk">
                Add a paper
              </Link>
            }
          >
            Papers
          </SectionHead>

          {selectedIds.length > 0 ? (
            <SelectionBar count={selectedIds.length}>
              <Num>
                {MAX_IDEA_SELECTION - selectedIds.length} more allowed
              </Num>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSelectedIds([]);
                  setSelectionMessage("");
                  clearGeneratedOutput();
                }}
                disabled={generationLoading}
              >
                Clear
              </Button>
            </SelectionBar>
          ) : null}

          {libraryLoading ? (
            <PageSkeleton rows={4} />
          ) : libraryError ? (
            <WarnPanel title="Your library did not load">{libraryError}</WarnPanel>
          ) : papers.length === 0 ? (
            <Empty>
              No papers yet. You can still generate ideas from a topic alone, or{" "}
              <Link href="/papers/new" className="lnk">
                add a paper
              </Link>
              .
            </Empty>
          ) : (
            papers.map((paper) => {
              const isSelected = selectedIds.includes(paper.id);
              const locked = !isSelected && selectedIds.length >= MAX_IDEA_SELECTION;

              return (
                <Item
                  key={paper.id}
                  checkbox={
                    <Checkbox
                      checked={isSelected}
                      onChange={() => handleTogglePaper(paper.id)}
                      disabled={locked || generationLoading}
                      label={`Use ${paper.title} as a source`}
                    />
                  }
                >
                  <h3>
                    <Link href={`/papers/${paper.id}`} className="lnk">
                      {paper.title}
                    </Link>
                  </h3>
                  {paper.authors ? <p className="auth">{paper.authors}</p> : null}
                  {paper.abstract ? <p className="abs">{paper.abstract}</p> : null}
                  <div className="metaline">
                    <Num>Added {formatDate(paper.created_at)}</Num>
                    {typeof paper.has_structured_breakdown === "boolean" ? (
                      <Tag tone={paper.has_structured_breakdown ? "default" : "quiet"}>
                        {paper.has_structured_breakdown
                          ? "breakdown ready"
                          : "no breakdown yet"}
                      </Tag>
                    ) : null}
                  </div>
                </Item>
              );
            })
          )}
        </Section>

        <Section>
          {generationError ? (
            <div style={{ marginBottom: "var(--space-lg)" }}>
              <Notice tone="bad">{generationError}</Notice>
            </div>
          ) : null}
          <Button onClick={handleGenerateIdeas} disabled={generationDisabled}>
            {generationLoading ? "Generating" : "Generate ideas"}
          </Button>
          {!hasSource && !generationLoading ? (
            <Provenance>
              Pick at least one paper or type a topic, then this runs.
            </Provenance>
          ) : null}
        </Section>

        {generationLoading ? (
          <Section>
            <Working>
              Reading the selected papers and drafting directions. This takes a
              minute.
            </Working>
          </Section>
        ) : null}

        {resultIsStale ? (
          <Section>
            <WarnPanel title="These ideas are from an older selection">
              The sources changed after this ran. Generate again to match what is
              selected now.
            </WarnPanel>
          </Section>
        ) : null}

        {showResult && ideaResult ? (
          <>
            {ideaResult.warnings.length > 0 ? (
              <Section>
                <WarnPanel
                  title={
                    ideaResult.warnings.length === 1
                      ? "One warning"
                      : `${ideaResult.warnings.length} warnings`
                  }
                >
                  {ideaResult.warnings.join(" ")}
                </WarnPanel>
              </Section>
            ) : null}

            <Section>
              <SectionHead>Built from</SectionHead>
              {ideaResult.selected_papers.length === 0 && !ideaResult.source_topic ? (
                <Empty>No source basis was returned.</Empty>
              ) : (
                <ChipRow>
                  {ideaResult.selected_papers.map((paper) => (
                    <Chip
                      key={paper.id}
                      href={`/papers/${paper.id}`}
                      title={paper.title}
                    >
                      {paper.title}
                    </Chip>
                  ))}
                  {ideaResult.source_topic ? (
                    <Chip>{ideaResult.source_topic}</Chip>
                  ) : null}
                </ChipRow>
              )}
            </Section>

            <Section>
              <SectionHead end={<Num>{ideaResult.ideas.length}</Num>}>
                Ideas
              </SectionHead>
              <Provenance>
                Written by the model from the papers above. Feasibility is its
                estimate, not a review.
              </Provenance>
              {ideaResult.ideas.length === 0 ? (
                <Empty>The model returned no ideas for these sources.</Empty>
              ) : (
                ideaResult.ideas.map((idea, index) => (
                  <IdeaEntry key={`${idea.title}-${index}`} idea={idea} index={index} />
                ))
              )}
            </Section>

            <Section>
              <SectionHead>Save this set</SectionHead>
              <div
                style={{
                  display: "flex",
                  gap: "var(--space-md)",
                  alignItems: "flex-start",
                  flexWrap: "wrap",
                }}
              >
                <Input
                  value={saveTitle}
                  maxLength={1000}
                  disabled={saveLoading}
                  onChange={(event) => {
                    setSaveTitle(event.target.value);
                    setSaveError("");
                    setSaveSuccess("");
                  }}
                  placeholder="Title for this set"
                  invalid={Boolean(saveError)}
                  style={{ flex: "1 1 320px" }}
                />
                <Button onClick={handleSaveIdeas} disabled={saveLoading}>
                  {saveLoading ? "Saving" : "Save"}
                </Button>
              </div>
              {saveError ? (
                <div style={{ marginTop: "var(--space-md)" }}>
                  <Notice tone="bad">{saveError}</Notice>
                </div>
              ) : null}
              {saveSuccess ? (
                <div style={{ marginTop: "var(--space-md)" }}>
                  <Notice>{saveSuccess}</Notice>
                </div>
              ) : null}
            </Section>
          </>
        ) : null}
      </Body>
    </>
  );
}

export default function IdeasPage() {
  return (
    <Suspense
      fallback={
        <>
          <TopBar crumb={<b>Ideas</b>} />
          <Body className="col-mid">
            <PageSkeleton />
          </Body>
        </>
      }
    >
      <IdeasPageContent />
    </Suspense>
  );
}
