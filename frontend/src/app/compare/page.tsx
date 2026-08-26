"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { useSearchParams } from "next/navigation";

import {
  Body,
  Button,
  Checkbox,
  Empty,
  Input,
  Item,
  Notice,
  Num,
  PageHeader,
  PageSkeleton,
  Panel,
  PanelBody,
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
import {
  MAX_COMPARE_SELECTION,
  getStoredCompareSelection,
  mergeCompareSelection,
  setStoredCompareSelection,
} from "@/lib/compare-selection";
import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PaperListItem {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
  has_structured_breakdown: boolean;
}

interface SelectedPaperResponse {
  id: string;
  title: string;
  authors: string | null;
  arxiv_url: string | null;
  created_at: string;
}

interface NormalizedProfile {
  paper_id: string;
  title: string;
  authors: string;
  problem: string;
  method: string;
  dataset_or_eval_setup: string;
  key_results: string;
  strengths: string;
  weaknesses: string;
  evidence_notes: Record<string, string[]>;
  warnings: string[];
}

interface ComparisonTableColumn {
  key: string;
  label: string;
}

interface ComparisonTableRow {
  key: string;
  label: string;
  values: string[];
}

interface CompareResponse {
  selected_papers: SelectedPaperResponse[];
  normalized_profiles: NormalizedProfile[];
  comparison_table: {
    columns: ComparisonTableColumn[];
    rows: ComparisonTableRow[];
  };
  narrative_summary: string;
  warnings: string[];
}

interface SaveComparisonResponse {
  id: string;
  title: string;
  item_type: "comparison";
  paper_ids: string[];
  created_at: string;
}

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

function buildCompareResultSignature(result: CompareResponse): string {
  return result.selected_papers.map((paper) => paper.id).join(",");
}

function createDefaultComparisonTitle(result: CompareResponse): string {
  const [firstPaper, secondPaper, ...remainingPapers] = result.selected_papers;
  if (!firstPaper || !secondPaper) {
    return "Comparison";
  }

  if (remainingPapers.length === 0) {
    return `Comparison: ${firstPaper.title} vs ${secondPaper.title}`;
  }

  return `Comparison: ${firstPaper.title} vs ${secondPaper.title} (+${remainingPapers.length} more)`;
}

function ComparePageContent() {
  const searchParams = useSearchParams();

  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(true);
  const [libraryError, setLibraryError] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const bootstrapKey = useRef<string | null>(null);
  const settled = useRef(false);
  const [selectionMessage, setSelectionMessage] = useState("");
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState("");
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null);
  const [lastComparedSignature, setLastComparedSignature] = useState("");
  const [saveTitle, setSaveTitle] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState("");
  const [lastSavedKey, setLastSavedKey] = useState("");

  /* The selection arrives from one of two places, or both: ?paper= in the URL
     and whatever was left in storage by Library or a paper page. The merge is
     written straight back, so this effect is idempotent and a second run reads
     its own result. */
  useEffect(() => {
    const merged = mergeCompareSelection(
      searchParams.getAll("paper"),
      getStoredCompareSelection(),
    );
    bootstrapKey.current = merged.join(",");
    settled.current = false;
    setStoredCompareSelection(merged);
    setSelectedIds(merged);
  }, [searchParams]);

  /* Nothing is written back until state actually holds what the bootstrap
     read. Without the guard this effect runs once with the empty initial
     value and erases the selection that brought the person here, and in
     development effects run twice, so it erases it every single time. */
  useEffect(() => {
    const key = selectedIds.join(",");

    if (!settled.current) {
      if (bootstrapKey.current !== null && key === bootstrapKey.current) {
        settled.current = true;
      }
      return;
    }

    setStoredCompareSelection(selectedIds);
  }, [selectedIds]);

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

  useEffect(() => {
    if (selectedIds.join(",") !== lastComparedSignature) {
      setCompareResult(null);
      setCompareError("");
    }
  }, [lastComparedSignature, selectedIds]);

  useEffect(() => {
    if (!compareResult) {
      setSaveTitle("");
      setSaveLoading(false);
      setSaveError("");
      setSaveSuccess("");
      setLastSavedKey("");
      return;
    }

    setSaveTitle(createDefaultComparisonTitle(compareResult));
    setSaveLoading(false);
    setSaveError("");
    setSaveSuccess("");
    setLastSavedKey("");
  }, [compareResult]);

  const selectedPapers = selectedIds
    .map((paperId) => papers.find((paper) => paper.id === paperId))
    .filter((paper): paper is PaperListItem => Boolean(paper));

  const selectedPapersNeedingProcessing = selectedPapers.filter(
    (paper) => !paper.has_structured_breakdown,
  );
  const compareResultSignature = compareResult
    ? buildCompareResultSignature(compareResult)
    : "";

  const profileById: Record<string, NormalizedProfile> = {};
  if (compareResult) {
    for (const profile of compareResult.normalized_profiles) {
      profileById[profile.paper_id] = profile;
    }
  }

  const handleTogglePaper = (paperId: string) => {
    if (compareLoading) {
      return;
    }

    let nextMessage = "";

    setSelectedIds((current) => {
      if (current.includes(paperId)) {
        return current.filter((id) => id !== paperId);
      }

      if (current.length >= MAX_COMPARE_SELECTION) {
        nextMessage = `Compare handles ${MAX_COMPARE_SELECTION} papers at a time. Deselect one to add another.`;
        return current;
      }

      return [...current, paperId];
    });

    setSelectionMessage(nextMessage);
  };

  const handleCompare = async () => {
    if (compareLoading) {
      return;
    }

    setCompareError("");
    setSelectionMessage("");

    if (selectedIds.length < 2) {
      setCompareError("Comparing needs at least two papers. Select one more.");
      return;
    }

    setCompareLoading(true);

    try {
      const res = await fetch(`${API_URL}/papers/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: selectedIds }),
      });

      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Comparison failed."));
      }

      const data: CompareResponse = await res.json();
      setCompareResult(data);
      setLastComparedSignature(selectedIds.join(","));
    } catch (err) {
      setCompareError(err instanceof Error ? err.message : "Comparison failed.");
    } finally {
      setCompareLoading(false);
    }
  };

  const handleSaveComparison = async () => {
    if (!compareResult) {
      return;
    }

    const normalizedTitle = saveTitle.trim();
    if (!normalizedTitle) {
      setSaveError("Give this comparison a title before saving.");
      setSaveSuccess("");
      return;
    }

    const saveKey = `${compareResultSignature}::${normalizedTitle}`;
    if (saveKey === lastSavedKey) {
      setSaveError("This comparison is already saved under that title.");
      setSaveSuccess("");
      return;
    }

    setSaveLoading(true);
    setSaveError("");
    setSaveSuccess("");

    try {
      const res = await fetch(`${API_URL}/papers/compare/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: normalizedTitle,
          paper_ids: compareResult.selected_papers.map((paper) => paper.id),
          comparison: compareResult,
        }),
      });

      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to save comparison."),
        );
      }

      const data: SaveComparisonResponse = await res.json();
      setSaveTitle(data.title);
      setSaveSuccess(`Saved to your library as "${data.title}".`);
      setLastSavedKey(saveKey);
    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to save comparison.",
      );
    } finally {
      setSaveLoading(false);
    }
  };

  return (
    <>
      <TopBar
        crumb={
          <>
            <b>Compare</b> <span aria-hidden>/</span>{" "}
            {selectedIds.length} paper{selectedIds.length === 1 ? "" : "s"} selected
          </>
        }
        end={
          compareResult ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSaveComparison}
              disabled={saveLoading}
            >
              {saveLoading ? "Saving" : "Save comparison"}
            </Button>
          ) : undefined
        }
      />
      <Body>
        <PageHeader
          title="Compare"
          sub="Put two to five papers side by side on the same set of dimensions. Nothing runs until you ask it to."
        />

        <Section>
          <SectionHead
            end={
              <Link href="/papers/new" className="lnk">
                Add paper
              </Link>
            }
          >
            Papers
          </SectionHead>

          {selectedIds.length > 0 ? (
            <SelectionBar count={selectedIds.length}>
              <Num>{MAX_COMPARE_SELECTION - selectedIds.length} more allowed</Num>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSelectedIds([]);
                  setSelectionMessage("");
                }}
                disabled={compareLoading}
              >
                Clear
              </Button>
            </SelectionBar>
          ) : null}

          {selectionMessage ? (
            <div style={{ marginTop: "var(--space-lg)" }}>
              <Notice tone="quiet">{selectionMessage}</Notice>
            </div>
          ) : null}

          {libraryLoading ? (
            <PageSkeleton rows={4} />
          ) : libraryError ? (
            <WarnPanel title="Your library did not load">{libraryError}</WarnPanel>
          ) : papers.length === 0 ? (
            <Empty>
              Nothing to compare yet.{" "}
              <Link href="/papers/new" className="lnk">
                Add a paper
              </Link>{" "}
              and come back.
            </Empty>
          ) : (
            papers.map((paper) => {
              const isSelected = selectedIds.includes(paper.id);
              const locked = !isSelected && selectedIds.length >= MAX_COMPARE_SELECTION;

              return (
                <Item
                  key={paper.id}
                  checkbox={
                    <Checkbox
                      checked={isSelected}
                      onChange={() => handleTogglePaper(paper.id)}
                      disabled={locked || compareLoading}
                      label={`Compare ${paper.title}`}
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
                    <Tag tone={paper.has_structured_breakdown ? "default" : "quiet"}>
                      {paper.has_structured_breakdown
                        ? "breakdown ready"
                        : "no breakdown yet"}
                    </Tag>
                  </div>
                </Item>
              );
            })
          )}
        </Section>

        {selectedPapersNeedingProcessing.length > 0 ? (
          <Section>
            <WarnPanel title="This run will take longer">
              {selectedPapersNeedingProcessing.map((paper) => paper.title).join(", ")}{" "}
              {selectedPapersNeedingProcessing.length === 1 ? "has" : "have"} no
              stored breakdown yet, so comparing will build{" "}
              {selectedPapersNeedingProcessing.length === 1 ? "it" : "them"} first.
            </WarnPanel>
          </Section>
        ) : null}

        <Section>
          {compareError ? (
            <div style={{ marginBottom: "var(--space-lg)" }}>
              <Notice tone="bad">{compareError}</Notice>
            </div>
          ) : null}
          <Button onClick={handleCompare} disabled={compareLoading || selectedIds.length < 2}>
            {compareLoading
              ? "Comparing"
              : `Compare ${Math.max(selectedIds.length, 2)} papers`}
          </Button>
        </Section>

        {compareLoading ? (
          <Section>
            <Working>
              Normalizing each paper onto the same dimensions, then building the
              matrix. This takes a minute.
            </Working>
          </Section>
        ) : null}

        {compareResult ? (
          <>
            {compareResult.warnings.length > 0 ? (
              <Section>
                <WarnPanel
                  title={
                    compareResult.warnings.length === 1
                      ? "One warning"
                      : `${compareResult.warnings.length} warnings`
                  }
                >
                  {compareResult.warnings.join(" ")}
                </WarnPanel>
              </Section>
            ) : null}

            <Section>
              <SectionHead
                end={<Num>{compareResult.selected_papers.length} papers</Num>}
              >
                Narrative summary
              </SectionHead>
              <Panel>
                <PanelBody>
                  <p>{compareResult.narrative_summary}</p>
                </PanelBody>
              </Panel>
              <Provenance>
                Written by the model from every breakdown below. Check it against
                the rows.
              </Provenance>
            </Section>

            <Section>
              <SectionHead>Comparison table</SectionHead>
              {compareResult.comparison_table.rows.length === 0 ? (
                <Empty>The comparison returned no rows.</Empty>
              ) : (
                <div className="cmp-table">
                  <table>
                    <thead>
                      <tr>
                        {compareResult.comparison_table.columns.map((column) => (
                          <th key={column.key} scope="col">
                            {column.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {compareResult.comparison_table.rows.map((row) => (
                        <tr key={row.key}>
                          <td>{row.label}</td>
                          {row.values.map((value, index) => (
                            <td key={`${row.key}-${index}`}>{value}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>

            <Section>
              <SectionHead>What was missing, per paper</SectionHead>
              {compareResult.selected_papers.map((paper) => {
                const profile = profileById[paper.id];
                return (
                  <Item key={paper.id}>
                    <h3>
                      <Link href={`/papers/${paper.id}`} className="lnk">
                        {paper.title}
                      </Link>
                    </h3>
                    {profile?.warnings.length ? (
                      <PlainList items={profile.warnings} />
                    ) : (
                      <p className="auth">Nothing was missing for this paper.</p>
                    )}
                  </Item>
                );
              })}
            </Section>

            <Section>
              <SectionHead>Save this comparison</SectionHead>
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
                  placeholder="Title for this comparison"
                  invalid={Boolean(saveError)}
                  style={{ flex: "1 1 320px" }}
                />
                <Button onClick={handleSaveComparison} disabled={saveLoading}>
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

export default function ComparePage() {
  return (
    <Suspense
      fallback={
        <>
          <TopBar crumb={<b>Compare</b>} />
          <Body>
            <PageSkeleton />
          </Body>
        </>
      }
    >
      <ComparePageContent />
    </Suspense>
  );
}
