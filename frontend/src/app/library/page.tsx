"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  Blank,
  Body,
  Button,
  Checkbox,
  Confirm,
  Empty,
  Field,
  Input,
  Item,
  Menu,
  Notice,
  Num,
  PageHeader,
  PageSkeleton,
  Panel,
  PanelHead,
  Row,
  Section,
  SectionHead,
  SelectionBar,
  StatusPill,
  Tag,
  Toolbar,
  TopBar,
  WarnPanel,
  Working,
  toneFor,
} from "@/components";
import type { MenuOption } from "@/components";
import { getApiErrorMessage } from "@/lib/api-errors";
import {
  MAX_COMPARE_SELECTION,
  setStoredCompareSelection,
} from "@/lib/compare-selection";
import { explainEmbedding, needsEmbedding, papersWord } from "@/lib/embedding";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LibraryPaper {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
  has_structured_breakdown: boolean;
  embedding_status: string;
  embedding_provider: string;
  embedding_model: string;
  embedded_at: string | null;
}

interface DiscoveryRunItem {
  id: string;
  question: string;
  status: string;
  created_at: string;
  num_results: number;
}

interface SourcePaper {
  id: string;
  title: string;
}

interface SavedItem {
  id: string;
  title: string;
  item_type: string;
  paper_ids: string[];
  created_at: string;
  source_papers: SourcePaper[];
}

type SortKey = "recent" | "oldest" | "title";
type StatusKey = "all" | "attention" | "ready" | "stale" | "missing" | "failed";

const SORTS: MenuOption[] = [
  { value: "recent", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "title", label: "Title A to Z" },
];

const STATUSES: MenuOption[] = [
  { value: "all", label: "Any status" },
  { value: "attention", label: "Needs re-embedding" },
  { value: "ready", label: "Ready" },
  { value: "stale", label: "Stale" },
  { value: "missing", label: "Not embedded" },
  { value: "failed", label: "Failed" },
];

const TYPE_LABELS: Record<string, string> = {
  comparison: "Comparison",
  idea: "Idea",
  implementation: "Implementation",
};

function formatDate(value: string | null): string {
  if (!value) {
    return "an unknown date";
  }
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

function formatType(value: string): string {
  return TYPE_LABELS[value] || value.replace(/_/g, " ");
}

function matchesStatus(paper: LibraryPaper, filter: StatusKey): boolean {
  if (filter === "all") {
    return true;
  }
  if (filter === "attention") {
    return needsEmbedding(paper.embedding_status);
  }
  return paper.embedding_status === filter;
}

export default function LibraryPage() {
  const router = useRouter();

  const [papers, setPapers] = useState<LibraryPaper[]>([]);
  const [runs, setRuns] = useState<DiscoveryRunItem[]>([]);
  const [saved, setSaved] = useState<SavedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("recent");
  const [status, setStatus] = useState<StatusKey>("all");

  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulk, setBulk] = useState<"" | "reembed" | "remove">("");
  const [removeConfirm, setRemoveConfirm] = useState(false);
  const [singleReembedId, setSingleReembedId] = useState<string | null>(null);
  const [paperError, setPaperError] = useState("");
  const [paperNotice, setPaperNotice] = useState("");

  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [renameError, setRenameError] = useState("");
  const [renamingItemId, setRenamingItemId] = useState<string | null>(null);
  const [deleteConfirmItemId, setDeleteConfirmItemId] = useState<string | null>(
    null,
  );
  const [deleteError, setDeleteError] = useState("");
  const [deletingItemId, setDeletingItemId] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState("");

  const load = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }
    setError("");

    try {
      const [papersRes, runsRes, savedRes] = await Promise.all([
        fetch(`${API_URL}/papers/`),
        fetch(`${API_URL}/discover/`),
        fetch(`${API_URL}/workspace/saved-items`),
      ]);

      if (!papersRes.ok) {
        throw new Error(
          await getApiErrorMessage(papersRes, "Failed to load your papers."),
        );
      }
      if (!runsRes.ok) {
        throw new Error(
          await getApiErrorMessage(runsRes, "Failed to load your discovery runs."),
        );
      }
      if (!savedRes.ok) {
        throw new Error(
          await getApiErrorMessage(savedRes, "Failed to load your saved work."),
        );
      }

      setPapers(await papersRes.json());
      setRuns(await runsRes.json());
      setSaved(await savedRes.json());
    } catch (err) {
      setPapers([]);
      setRuns([]);
      setSaved([]);
      setError(err instanceof Error ? err.message : "Failed to load your library.");
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const visiblePapers = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = papers.filter((paper) => {
      if (!matchesStatus(paper, status)) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${paper.title} ${paper.authors ?? ""}`.toLowerCase().includes(needle);
    });

    const sorted = [...filtered];
    if (sort === "title") {
      sorted.sort((a, b) => a.title.localeCompare(b.title));
    } else if (sort === "oldest") {
      sorted.sort((a, b) => a.created_at.localeCompare(b.created_at));
    } else {
      sorted.sort((a, b) => b.created_at.localeCompare(a.created_at));
    }
    return sorted;
  }, [papers, query, sort, status]);

  const staleCount = useMemo(
    () => papers.filter((paper) => needsEmbedding(paper.embedding_status)).length,
    [papers],
  );

  /* Selection survives filtering, but every action reads it through this, so
     a paper hidden by the current filter is never acted on by surprise. */
  const selectedVisible = useMemo(
    () => visiblePapers.filter((paper) => selectedIds.includes(paper.id)),
    [visiblePapers, selectedIds],
  );

  const savedByType = useMemo(() => {
    const grouped: Record<string, SavedItem[]> = {};
    for (const item of saved) {
      if (!grouped[item.item_type]) {
        grouped[item.item_type] = [];
      }
      grouped[item.item_type].push(item);
    }
    return grouped;
  }, [saved]);

  const busy = bulk !== "" || singleReembedId !== null;

  const toggleSelected = (paperId: string) => {
    setPaperError("");
    setPaperNotice("");
    setRemoveConfirm(false);
    setSelectedIds((current) =>
      current.includes(paperId)
        ? current.filter((id) => id !== paperId)
        : [...current, paperId],
    );
  };

  const allVisibleSelected =
    visiblePapers.length > 0 && selectedVisible.length === visiblePapers.length;

  const toggleAllVisible = () => {
    setPaperError("");
    setPaperNotice("");
    setRemoveConfirm(false);
    setSelectedIds(allVisibleSelected ? [] : visiblePapers.map((paper) => paper.id));
  };

  const clearSelection = () => {
    setSelectedIds([]);
    setRemoveConfirm(false);
    setPaperError("");
  };

  const compareSelected = () => {
    setStoredCompareSelection(selectedVisible.map((paper) => paper.id));
    router.push("/compare");
  };

  /* force: true, because the person picked these papers by hand. Without it
     the endpoint skips anything already current, and a button that can
     silently do nothing is worse than one that costs a few tokens. */
  const reembedSelected = async () => {
    setBulk("reembed");
    setPaperError("");
    setPaperNotice("");

    try {
      const res = await fetch(`${API_URL}/papers/reembed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          paper_ids: selectedVisible.map((paper) => paper.id),
          force: true,
        }),
      });
      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Failed to re-embed."));
      }

      const data: { reembedded_count: number } = await res.json();
      setPaperNotice(`Re-embedded ${papersWord(data.reembedded_count)}.`);
      setSelectedIds([]);
      await load(false);
    } catch (err) {
      setPaperError(err instanceof Error ? err.message : "Failed to re-embed.");
    } finally {
      setBulk("");
    }
  };

  /* No paper_ids and force: false means "everything that is not current",
     which is exactly what the warning above the list is about. */
  const reembedEverythingStale = async () => {
    setBulk("reembed");
    setPaperError("");
    setPaperNotice("");

    try {
      const res = await fetch(`${API_URL}/papers/reembed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force: false }),
      });
      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Failed to re-embed."));
      }

      const data: { reembedded_count: number; skipped_count: number } =
        await res.json();
      setPaperNotice(
        `Re-embedded ${papersWord(data.reembedded_count)}. ${data.skipped_count} were already current.`,
      );
      await load(false);
    } catch (err) {
      setPaperError(err instanceof Error ? err.message : "Failed to re-embed.");
    } finally {
      setBulk("");
    }
  };

  const reembedOne = async (paper: LibraryPaper) => {
    setSingleReembedId(paper.id);
    setPaperError("");
    setPaperNotice("");

    try {
      const res = await fetch(`${API_URL}/papers/${paper.id}/reembed`, {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Failed to re-embed."));
      }
      setPaperNotice(`Re-embedded ${paper.title}.`);
      await load(false);
    } catch (err) {
      setPaperError(err instanceof Error ? err.message : "Failed to re-embed.");
    } finally {
      setSingleReembedId(null);
    }
  };

  /* One request per paper: the API deletes one at a time, and stopping at the
     first failure leaves a state the person can see and retry from. */
  const removeSelected = async () => {
    setBulk("remove");
    setPaperError("");
    setPaperNotice("");

    const targets = selectedVisible;
    let removed = 0;

    try {
      for (const paper of targets) {
        const res = await fetch(`${API_URL}/papers/${paper.id}`, {
          method: "DELETE",
        });
        if (!res.ok) {
          throw new Error(
            await getApiErrorMessage(res, `Failed to remove ${paper.title}.`),
          );
        }
        removed += 1;
      }
      setPaperNotice(`Removed ${papersWord(removed)}.`);
      setSelectedIds([]);
      setRemoveConfirm(false);
    } catch (err) {
      setPaperError(
        `${err instanceof Error ? err.message : "Failed to remove papers."}${
          removed > 0 ? ` ${papersWord(removed)} were removed before this.` : ""
        }`,
      );
    } finally {
      setBulk("");
      await load(false);
    }
  };

  const beginRename = (item: SavedItem) => {
    setEditingItemId(item.id);
    setRenameTitle(item.title);
    setRenameError("");
    setDeleteError("");
    setDeleteConfirmItemId(null);
    setSavedNotice("");
  };

  const cancelRename = () => {
    setEditingItemId(null);
    setRenameTitle("");
    setRenameError("");
  };

  const renameItem = async (item: SavedItem) => {
    const title = renameTitle.trim();
    if (!title) {
      setRenameError("Give this saved item a title before saving.");
      return;
    }

    setRenamingItemId(item.id);
    setRenameError("");
    setSavedNotice("");

    try {
      const res = await fetch(`${API_URL}/workspace/saved-items/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to rename saved item."),
        );
      }

      cancelRename();
      setSavedNotice("Renamed.");
      await load(false);
    } catch (err) {
      setRenameError(
        err instanceof Error ? err.message : "Failed to rename saved item.",
      );
    } finally {
      setRenamingItemId(null);
    }
  };

  const requestDelete = (item: SavedItem) => {
    setDeleteConfirmItemId(item.id);
    setDeleteError("");
    setEditingItemId(null);
    setRenameError("");
    setSavedNotice("");
  };

  const deleteItem = async (item: SavedItem) => {
    setDeletingItemId(item.id);
    setDeleteError("");
    setSavedNotice("");

    try {
      const res = await fetch(`${API_URL}/workspace/saved-items/${item.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to delete saved item."),
        );
      }

      setDeleteConfirmItemId(null);
      setSavedNotice("Deleted.");
      await load(false);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete saved item.",
      );
    } finally {
      setDeletingItemId(null);
    }
  };

  if (loading) {
    return (
      <>
        <TopBar crumb={<b>Library</b>} />
        <Body>
          <PageSkeleton />
        </Body>
      </>
    );
  }

  if (error) {
    return (
      <>
        <TopBar crumb={<b>Library</b>} />
        <Body>
          <Blank
            kind="Cannot open"
            title="Your library could not be loaded"
            actions={
              <>
                <Button onClick={() => load()}>Try again</Button>
                <Link href="/" className="btn ghost">
                  Go to Discover
                </Link>
              </>
            }
          >
            {error} PaperTrail talks to a local server on port 8000; if it is not
            running, start it and try again.
          </Blank>
        </Body>
      </>
    );
  }

  const empty = papers.length === 0 && runs.length === 0 && saved.length === 0;
  const compareReady =
    selectedVisible.length >= 2 && selectedVisible.length <= MAX_COMPARE_SELECTION;

  return (
    <>
      <TopBar
        crumb={<b>Library</b>}
        end={
          empty ? undefined : (
            <>
              <Num>{papersWord(papers.length)}</Num>
              <Link href="/papers/new" className="btn sm">
                Add paper
              </Link>
            </>
          )
        }
      />
      <Body>
        <PageHeader
          title="Library"
          sub="Every paper you have brought in, and what PaperTrail has managed to do with each one."
        />

        {empty ? (
          <Section>
            <Blank
              kind="Nothing here yet"
              quiet
              title="Your library is empty"
              actions={
                <>
                  <Link href="/" className="btn">
                    Start with a question
                  </Link>
                  <Link href="/papers/new" className="btn ghost">
                    Add a paper
                  </Link>
                </>
              }
            >
              Begin from a research question and let discovery find papers, or add
              a paper you already have. Compare and Ideas open up once there are
              papers here.
            </Blank>
          </Section>
        ) : (
          <>
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

              {staleCount > 0 ? (
                <WarnPanel
                  title={`${papersWord(staleCount)} are not embedded with the model you have set`}
                  actions={
                    bulk === "reembed" ? (
                      <Working>Re-embedding, one request per paper</Working>
                    ) : (
                      <>
                        <Button size="sm" onClick={reembedEverythingStale}>
                          Re-embed them
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setStatus("attention")}
                        >
                          Show only those
                        </Button>
                      </>
                    )
                  }
                >
                  Chat and comparison read whatever was embedded last, so answers
                  drawn from these papers can disagree with the rest of your
                  library. Re-embedding sends their text to the embedding provider
                  again and costs tokens.
                </WarnPanel>
              ) : null}

              {papers.length === 0 ? (
                <Empty>
                  No papers yet.{" "}
                  <Link href="/papers/new" className="lnk">
                    Add one
                  </Link>{" "}
                  to get started.
                </Empty>
              ) : (
                <>
                  <Toolbar>
                    <Input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Search titles and authors"
                      aria-label="Search papers by title or author"
                      type="search"
                    />
                    <Menu
                      label="Filter by embedding status"
                      value={status}
                      onChange={(value) => setStatus(value as StatusKey)}
                      options={STATUSES}
                    />
                    <Menu
                      label="Sort papers"
                      value={sort}
                      onChange={(value) => setSort(value as SortKey)}
                      options={SORTS}
                    />
                    <span className="spacer" />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={toggleAllVisible}
                      disabled={visiblePapers.length === 0 || busy}
                    >
                      {allVisibleSelected ? "Clear selection" : "Select all"}
                    </Button>
                  </Toolbar>

                  {selectedVisible.length > 0 ? (
                    <div style={{ marginTop: "var(--space-lg)" }}>
                      <SelectionBar count={selectedVisible.length}>
                        <Button
                          size="sm"
                          onClick={compareSelected}
                          disabled={!compareReady || busy}
                          title={
                            compareReady
                              ? undefined
                              : `Comparison takes 2 to ${MAX_COMPARE_SELECTION} papers.`
                          }
                        >
                          Compare
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={reembedSelected}
                          disabled={busy}
                        >
                          {bulk === "reembed" ? "Re-embedding" : "Re-embed"}
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => setRemoveConfirm(true)}
                          disabled={busy || removeConfirm}
                        >
                          Remove
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={clearSelection}
                          disabled={busy}
                        >
                          Clear
                        </Button>
                      </SelectionBar>
                    </div>
                  ) : null}

                  {removeConfirm ? (
                    <div style={{ marginTop: "var(--space-lg)" }}>
                      <Confirm
                        title={`Remove ${papersWord(selectedVisible.length)} from your library?`}
                        actions={
                          <>
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={removeSelected}
                              disabled={bulk === "remove"}
                            >
                              {bulk === "remove" ? "Removing" : "Remove"}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setRemoveConfirm(false)}
                              disabled={bulk === "remove"}
                            >
                              Keep them
                            </Button>
                          </>
                        }
                      >
                        The paper, its sections, its breakdown, its chat history,
                        and its embeddings all go. Saved comparisons and idea sets
                        that named it stay, but they will no longer link back.
                      </Confirm>
                    </div>
                  ) : null}

                  {paperError ? (
                    <div style={{ marginTop: "var(--space-lg)" }}>
                      <Notice tone="bad">{paperError}</Notice>
                    </div>
                  ) : null}
                  {paperNotice ? (
                    <div style={{ marginTop: "var(--space-lg)" }}>
                      <Notice>{paperNotice}</Notice>
                    </div>
                  ) : null}

                  {visiblePapers.length === 0 ? (
                    <Empty>
                      No paper here matches that.{" "}
                      <button
                        type="button"
                        className="lnk"
                        onClick={() => {
                          setQuery("");
                          setStatus("all");
                        }}
                      >
                        Clear the filters
                      </button>{" "}
                      to see all {papersWord(papers.length)}.
                    </Empty>
                  ) : (
                    visiblePapers.map((paper) => (
                      <Item
                        key={paper.id}
                        checkbox={
                          <Checkbox
                            checked={selectedIds.includes(paper.id)}
                            onChange={() => toggleSelected(paper.id)}
                            label={`Select ${paper.title}`}
                            disabled={busy}
                          />
                        }
                      >
                        <h3>
                          <Link href={`/papers/${paper.id}`} className="lnk">
                            {paper.title}
                          </Link>
                        </h3>
                        {paper.authors ? (
                          <p className="auth">{paper.authors}</p>
                        ) : null}
                        <div className="metaline">
                          <Num>Added {formatDate(paper.created_at)}</Num>
                          <StatusPill tone={toneFor(paper.embedding_status)}>
                            {paper.embedding_status}
                          </StatusPill>
                          <Tag
                            tone={paper.has_structured_breakdown ? "default" : "quiet"}
                          >
                            {paper.has_structured_breakdown
                              ? "breakdown ready"
                              : "no breakdown yet"}
                          </Tag>
                          {needsEmbedding(paper.embedding_status) ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => reembedOne(paper)}
                              disabled={busy}
                              title={explainEmbedding(paper.embedding_status)}
                            >
                              {singleReembedId === paper.id
                                ? "Re-embedding"
                                : "Re-embed"}
                            </Button>
                          ) : null}
                        </div>
                      </Item>
                    ))
                  )}
                </>
              )}
            </Section>

            <Section>
              <SectionHead
                end={
                  <Link href="/" className="lnk">
                    New search
                  </Link>
                }
              >
                Discovery runs
              </SectionHead>
              {runs.length === 0 ? (
                <Empty>
                  No discovery runs yet.{" "}
                  <Link href="/" className="lnk">
                    Ask a research question
                  </Link>{" "}
                  to start one.
                </Empty>
              ) : (
                <Panel>
                  <PanelHead end={<Num>{runs.length} total</Num>}>Runs</PanelHead>
                  {runs.map((run) => (
                    <Row
                      key={run.id}
                      href={`/discover/${run.id}`}
                      end={
                        <>
                          <Num>{run.num_results}</Num>
                          <StatusPill tone={toneFor(run.status)}>
                            {run.status}
                          </StatusPill>
                        </>
                      }
                    >
                      {run.question}
                      <span className="sub">Run on {formatDate(run.created_at)}</span>
                    </Row>
                  ))}
                </Panel>
              )}
            </Section>

            <Section>
              <SectionHead
                end={savedNotice ? <Notice>{savedNotice}</Notice> : undefined}
              >
                Saved work
              </SectionHead>
              {saved.length === 0 ? (
                <Empty>
                  Nothing saved yet. Comparisons, idea sets, and implementation
                  plans land here once you save one.
                </Empty>
              ) : (
                Object.entries(savedByType).map(([itemType, items]) => (
                  <div key={itemType} style={{ marginTop: "var(--space-3xl)" }}>
                    <SectionHead level={3} end={<Num>{items.length}</Num>}>
                      {formatType(itemType)}
                    </SectionHead>
                    {items.map((item) => (
                      <Item key={item.id}>
                        {editingItemId === item.id ? (
                          <form
                            onSubmit={(event) => {
                              event.preventDefault();
                              renameItem(item);
                            }}
                          >
                            <Field label="Title" error={renameError || undefined}>
                              <Input
                                value={renameTitle}
                                onChange={(event) =>
                                  setRenameTitle(event.target.value)
                                }
                                disabled={renamingItemId === item.id}
                                invalid={Boolean(renameError)}
                                maxLength={1000}
                                autoFocus
                              />
                            </Field>
                            <div
                              style={{
                                display: "flex",
                                gap: "var(--space-md)",
                                marginTop: "var(--space-lg)",
                              }}
                            >
                              <Button
                                type="submit"
                                size="sm"
                                disabled={renamingItemId === item.id}
                              >
                                {renamingItemId === item.id ? "Saving" : "Save"}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={cancelRename}
                                disabled={renamingItemId === item.id}
                              >
                                Cancel
                              </Button>
                            </div>
                          </form>
                        ) : (
                          <>
                            <h3>
                              <Link
                                href={`/library/saved/${item.id}`}
                                className="lnk"
                              >
                                {item.title}
                              </Link>
                            </h3>
                            <p className="auth">
                              {item.source_papers.length > 0
                                ? item.source_papers.map((p) => p.title).join(", ")
                                : "No source papers on record"}
                            </p>
                            <div className="metaline">
                              <Num>Saved {formatDate(item.created_at)}</Num>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => beginRename(item)}
                                disabled={deletingItemId === item.id}
                              >
                                Rename
                              </Button>
                              <Button
                                variant="danger"
                                size="sm"
                                onClick={() => requestDelete(item)}
                                disabled={
                                  deletingItemId === item.id ||
                                  deleteConfirmItemId === item.id
                                }
                              >
                                Delete
                              </Button>
                            </div>
                          </>
                        )}

                        {deleteConfirmItemId === item.id ? (
                          <div style={{ marginTop: "var(--space-lg)" }}>
                            <Confirm
                              title="Delete this saved item?"
                              error={deleteError || undefined}
                              actions={
                                <>
                                  <Button
                                    variant="danger"
                                    size="sm"
                                    onClick={() => deleteItem(item)}
                                    disabled={deletingItemId === item.id}
                                  >
                                    {deletingItemId === item.id
                                      ? "Deleting"
                                      : "Delete"}
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setDeleteConfirmItemId(null)}
                                    disabled={deletingItemId === item.id}
                                  >
                                    Keep it
                                  </Button>
                                </>
                              }
                            >
                              The source papers and the run that produced this stay
                              in your library. Only this saved copy goes.
                            </Confirm>
                          </div>
                        ) : null}
                      </Item>
                    ))}
                  </div>
                ))
              )}
            </Section>
          </>
        )}
      </Body>
    </>
  );
}
