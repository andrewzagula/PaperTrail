"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import {
  Blank,
  Body,
  Button,
  Chip,
  ChipRow,
  Cite,
  CodeBlock,
  Confirm,
  Empty,
  Fact,
  Facts,
  Field,
  Input,
  Notice,
  Num,
  PageHeader,
  PageSkeleton,
  Panel,
  PanelBody,
  PlainList,
  Score,
  Section,
  SectionHead,
  Step,
  Tag,
  TopBar,
  WarnPanel,
} from "@/components";
import type { TagTone } from "@/components";
import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type JsonRecord = Record<string, unknown>;

interface WorkspaceSourcePaper {
  id: string;
  title: string;
  authors: string | null;
  arxiv_url: string | null;
  created_at: string;
}

interface WorkspaceSavedItemSummary {
  id: string;
  title: string;
  item_type: string;
  paper_ids: string[];
  created_at: string;
  source_papers: WorkspaceSourcePaper[];
}

interface WorkspaceSavedItemDetail extends WorkspaceSavedItemSummary {
  data: JsonRecord;
}

const TYPE_LABELS: Record<string, string> = {
  comparison: "Comparison",
  idea: "Idea",
  implementation: "Implementation",
};

const TRANSFORMATION_LABELS: Record<string, string> = {
  combine: "Combine",
  ablate: "Ablate",
  extend: "Extend",
  apply: "Apply",
};

/* Severity reads straight through: a high-severity gap is the one to look
   at first. Feasibility runs the other way, so it is inverted here rather
   than at every call site: a low-feasibility idea is the alarming one. */
const SEVERITY_TONES: Record<string, TagTone> = {
  high: "high",
  medium: "med",
  low: "quiet",
};

const FEASIBILITY_TONES: Record<string, TagTone> = {
  low: "high",
  medium: "med",
  high: "default",
};

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown, fallback = ""): string {
  if (typeof value === "string") {
    return value.trim() || fallback;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  return fallback;
}

function getString(record: JsonRecord, key: string, fallback = ""): string {
  return asString(record[key], fallback);
}

function getRecord(record: JsonRecord, key: string): JsonRecord {
  const value = record[key];
  return isRecord(value) ? value : {};
}

function getRecordArray(record: JsonRecord, key: string): JsonRecord[] {
  const value = record[key];
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    const singleValue = asString(value);
    return singleValue ? [singleValue] : [];
  }

  return value.map((item) => asString(item)).filter((item) => item.length > 0);
}

function getStringArray(record: JsonRecord, key: string): string[] {
  return asStringArray(record[key]);
}

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

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "Payload could not be serialized.";
  }
}

async function copyTextToClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {}
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  const copied = document.execCommand("copy");
  document.body.removeChild(textarea);

  if (!copied) {
    throw new Error("Copy failed");
  }
}

/* ------------------------------------------------------------------
   Shared pieces
   ------------------------------------------------------------------ */

/** Every renderer reports the model's own caveats before its output. */
function Warnings({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <Section>
      <WarnPanel
        title={warnings.length === 1 ? "One warning" : `${warnings.length} warnings`}
      >
        {warnings.join(" ")}
      </WarnPanel>
    </Section>
  );
}

function PaperChips({ papers }: { papers: JsonRecord[] }) {
  return (
    <ChipRow>
      {papers.map((paper, index) => {
        const id = getString(paper, "id");
        const title = getString(paper, "title", "Untitled paper");
        return (
          <Chip
            key={id || `${title}-${index}`}
            href={id ? `/papers/${id}` : undefined}
            title={title}
          >
            {title}
          </Chip>
        );
      })}
    </ChipRow>
  );
}

function ListFact({ k, items }: { k: string; items: string[] }) {
  return (
    <Fact k={k} none="None returned.">
      {items.length > 0 ? <PlainList items={items} /> : null}
    </Fact>
  );
}

/* ------------------------------------------------------------------
   Comparison
   ------------------------------------------------------------------ */

const PROFILE_FIELDS: [string, string][] = [
  ["Problem", "problem"],
  ["Method", "method"],
  ["Dataset or eval setup", "dataset_or_eval_setup"],
  ["Key results", "key_results"],
  ["Strengths", "strengths"],
  ["Weaknesses", "weaknesses"],
];

function ProfileEntry({ profile }: { profile: JsonRecord }) {
  const evidenceNotes = getRecord(profile, "evidence_notes");
  const warnings = getStringArray(profile, "warnings");
  const authors = getString(profile, "authors");

  return (
    <div className="item flush">
      <div>
        <h3>{getString(profile, "title", "Untitled profile")}</h3>
        {authors ? <p className="auth">{authors}</p> : null}
        <div style={{ marginTop: "var(--space-xl)" }}>
          <Facts>
            {PROFILE_FIELDS.map(([label, key]) => (
              <Fact key={key} k={label}>
                {getString(profile, key) || undefined}
              </Fact>
            ))}
            {Object.entries(evidenceNotes).map(([key, value]) => (
              <ListFact
                key={key}
                k={`Evidence: ${key.replace(/_/g, " ")}`}
                items={asStringArray(value)}
              />
            ))}
            {warnings.length > 0 ? (
              <ListFact k="Profile warnings" items={warnings} />
            ) : null}
          </Facts>
        </div>
      </div>
    </div>
  );
}

function ComparisonView({ data }: { data: JsonRecord }) {
  const selectedPapers = getRecordArray(data, "selected_papers");
  const profiles = getRecordArray(data, "normalized_profiles");
  const table = getRecord(data, "comparison_table");
  const columns = getRecordArray(table, "columns");
  const rows = getRecordArray(table, "rows");
  const warnings = getStringArray(data, "warnings");
  const narrativeSummary = getString(data, "narrative_summary");

  return (
    <>
      <Warnings warnings={warnings} />

      {selectedPapers.length > 0 ? (
        <Section>
          <SectionHead>Papers compared</SectionHead>
          <PaperChips papers={selectedPapers} />
        </Section>
      ) : null}

      <Section>
        <SectionHead>Narrative summary</SectionHead>
        {narrativeSummary ? (
          <div className="reading">
            <p style={{ whiteSpace: "pre-wrap" }}>{narrativeSummary}</p>
          </div>
        ) : (
          <Empty>No narrative summary was stored.</Empty>
        )}
      </Section>

      <Section>
        <SectionHead>Comparison table</SectionHead>
        {columns.length === 0 || rows.length === 0 ? (
          <Empty>No comparison table was stored.</Empty>
        ) : (
          <div className="cmp-table">
            <table>
              <thead>
                <tr>
                  {columns.map((column, index) => (
                    <th key={getString(column, "key") || index} scope="col">
                      {getString(column, "label", `Column ${index + 1}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rowIndex) => {
                  const values = getStringArray(row, "values");
                  return (
                    <tr key={getString(row, "key") || rowIndex}>
                      <td>{getString(row, "label", `Row ${rowIndex + 1}`)}</td>
                      {values.map((value, valueIndex) => (
                        <td key={`${rowIndex}-${valueIndex}`}>{value}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section>
        <SectionHead>Paper profiles</SectionHead>
        {profiles.length === 0 ? (
          <Empty>No normalized paper profiles were stored.</Empty>
        ) : (
          profiles.map((profile, index) => (
            <ProfileEntry
              key={getString(profile, "paper_id") || index}
              profile={profile}
            />
          ))
        )}
      </Section>
    </>
  );
}

/* ------------------------------------------------------------------
   Ideas
   ------------------------------------------------------------------ */

function IdeaEntry({ idea, index }: { idea: JsonRecord; index: number }) {
  const transformationType = getString(idea, "transformation_type");
  const feasibility = getString(idea, "feasibility");
  const critique = getString(idea, "critique");
  const score = getString(idea, "score");
  const warnings = getStringArray(idea, "warnings");

  return (
    <div className="item">
      <div className="rank">{index + 1}</div>
      <div>
        <h3>{getString(idea, "title", "Untitled idea")}</h3>
        <div className="foot" style={{ marginTop: "var(--space-md)" }}>
          {transformationType ? (
            <Tag>
              {TRANSFORMATION_LABELS[transformationType] || transformationType}
            </Tag>
          ) : null}
          {feasibility ? (
            <Tag tone={FEASIBILITY_TONES[feasibility] ?? "default"}>
              {feasibility} feasibility
            </Tag>
          ) : null}
          {score ? <Score>{score}</Score> : null}
        </div>
        <div style={{ marginTop: "var(--space-xl)" }}>
          <Facts>
            <Fact k="Description">{getString(idea, "description") || undefined}</Fact>
            <Fact k="Why interesting">
              {getString(idea, "why_interesting") || undefined}
            </Fact>
            {critique ? <Fact k="Critique">{critique}</Fact> : null}
            <ListFact k="Evidence basis" items={getStringArray(idea, "evidence_basis")} />
            <ListFact
              k="Risks or unknowns"
              items={getStringArray(idea, "risks_or_unknowns")}
            />
            {warnings.length > 0 ? <ListFact k="Warnings" items={warnings} /> : null}
          </Facts>
        </div>
      </div>
    </div>
  );
}

function IdeaView({ data }: { data: JsonRecord }) {
  const selectedPapers = getRecordArray(data, "selected_papers");
  const sourceTopic = getString(data, "source_topic");
  const ideas = getRecordArray(data, "ideas");
  const warnings = getStringArray(data, "warnings");
  const hasBasis = selectedPapers.length > 0 || Boolean(sourceTopic);

  return (
    <>
      <Warnings warnings={warnings} />

      <Section>
        <SectionHead>Source basis</SectionHead>
        {hasBasis ? (
          <ChipRow>
            {selectedPapers.map((paper, index) => {
              const id = getString(paper, "id");
              const title = getString(paper, "title", "Untitled paper");
              return (
                <Chip
                  key={id || `${title}-${index}`}
                  href={id ? `/papers/${id}` : undefined}
                  title={title}
                >
                  {title}
                </Chip>
              );
            })}
            {sourceTopic ? <Chip>{sourceTopic}</Chip> : null}
          </ChipRow>
        ) : (
          <Empty>No source basis was stored.</Empty>
        )}
      </Section>

      <Section>
        <SectionHead
          end={ideas.length > 0 ? <Num>{ideas.length} ideas</Num> : undefined}
        >
          Ideas
        </SectionHead>
        {ideas.length === 0 ? (
          <Empty>No generated ideas were stored.</Empty>
        ) : (
          ideas.map((idea, index) => (
            <IdeaEntry
              key={`${getString(idea, "title")}-${index}`}
              idea={idea}
              index={index}
            />
          ))
        )}
      </Section>
    </>
  );
}

/* ------------------------------------------------------------------
   Implementation

   One continuous page, the same shape as /papers/[id]/implement.
   A saved plan is read start to finish, so it is not put behind tabs.
   ------------------------------------------------------------------ */

/** Inputs and outputs, labelled inline, as quiet chips. */
function Io({ k, items }: { k: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <>
      <span className="k">{k}</span>
      {items.map((item, index) => (
        <Tag key={`${item}-${index}`} tone="quiet">
          {item}
        </Tag>
      ))}
    </>
  );
}

function ImplementationView({ data }: { data: JsonRecord }) {
  const [copied, setCopied] = useState<Record<string, string>>({});
  const paper = getRecord(data, "paper");
  const warnings = getStringArray(data, "warnings");
  const steps = getRecordArray(data, "algorithm_steps");
  const gaps = getRecordArray(data, "assumptions_and_gaps");
  const files = getRecordArray(data, "starter_code");
  const sourceSections = getRecordArray(data, "source_sections");
  const pseudocode = getString(data, "pseudocode");
  const setup = getStringArray(data, "setup_notes");
  const plan = getStringArray(data, "test_plan");

  const copy = async (path: string, content: string) => {
    try {
      await copyTextToClipboard(content);
      setCopied((current) => ({ ...current, [path]: "Copied" }));
    } catch {
      setCopied((current) => ({ ...current, [path]: "Copy failed" }));
    }
  };

  return (
    <>
      <Warnings warnings={warnings} />

      {Object.keys(paper).length > 0 ? (
        <Section>
          <SectionHead>Source paper</SectionHead>
          <PaperChips papers={[paper]} />
        </Section>
      ) : null}

      <Section>
        <SectionHead>Summary</SectionHead>
        <div className="reading">
          <p>
            {getString(
              data,
              "implementation_summary",
              "No implementation summary was stored.",
            )}
          </p>
        </div>
      </Section>

      <Section className="col-narrow">
        <SectionHead
          end={<Num>{steps.length} step{steps.length === 1 ? "" : "s"}</Num>}
        >
          Algorithm steps
        </SectionHead>
        {steps.length === 0 ? (
          <Empty>No grounded algorithm steps were stored.</Empty>
        ) : (
          steps.map((step, index) => {
            const evidence = getStringArray(step, "evidence");
            const inputs = getStringArray(step, "inputs");
            const outputs = getStringArray(step, "outputs");
            return (
              <Step
                key={`${getString(step, "order")}-${index}`}
                n={getString(step, "order", String(index + 1)).padStart(2, "0")}
                title={getString(step, "title", "Untitled step")}
              >
                <p>{getString(step, "description", "No description returned.")}</p>
                {inputs.length > 0 || outputs.length > 0 ? (
                  <div className="io">
                    <Io k="in" items={inputs} />
                    <Io k="out" items={outputs} />
                  </div>
                ) : null}
                {evidence.length > 0 ? <Cite>{evidence.join(" · ")}</Cite> : null}
              </Step>
            );
          })
        )}
      </Section>

      <Section className="col-narrow">
        <SectionHead end={<Num>{gaps.length} found</Num>}>
          Assumptions and gaps
        </SectionHead>
        {gaps.length === 0 ? (
          <Empty>No assumptions or gaps were stored.</Empty>
        ) : (
          gaps.map((gap, index) => {
            const severity = getString(gap, "severity");
            const evidence = getStringArray(gap, "evidence");
            return (
              <div key={`${getString(gap, "category")}-${index}`} className="gap-item">
                <div className="top">
                  <b>{getString(gap, "category", "uncategorized").replace(/_/g, " ")}</b>
                  {severity ? (
                    <Tag tone={SEVERITY_TONES[severity] ?? "default"}>{severity}</Tag>
                  ) : null}
                </div>
                <p>{getString(gap, "description", "No description returned.")}</p>
                {evidence.length > 0 ? <Cite>{evidence.join(" · ")}</Cite> : null}
              </div>
            );
          })
        )}
      </Section>

      <Section className="col-narrow">
        <SectionHead>Pseudocode</SectionHead>
        {pseudocode ? (
          <CodeBlock path="pseudocode" content={pseudocode} />
        ) : (
          <Empty>No pseudocode was stored.</Empty>
        )}
      </Section>

      <Section className="col-narrow">
        <SectionHead
          end={<Num>{files.length} file{files.length === 1 ? "" : "s"}</Num>}
        >
          Starter code
        </SectionHead>
        {files.length === 0 ? (
          <Empty>No starter code files were stored.</Empty>
        ) : (
          files.map((file, index) => {
            const path = getString(file, "path", `file-${index + 1}`);
            const content = getString(file, "content", "No content returned.");
            const status = copied[path];
            return (
              <CodeBlock
                key={`${path}-${index}`}
                path={path}
                purpose={getString(file, "purpose") || undefined}
                content={content}
                end={
                  <>
                    {status ? (
                      <Notice tone={status === "Copied" ? "quiet" : "bad"}>
                        {status}
                      </Notice>
                    ) : null}
                    <Button variant="ghost" size="sm" onClick={() => copy(path, content)}>
                      Copy
                    </Button>
                  </>
                }
              />
            );
          })
        )}
      </Section>

      <Section className="col-narrow">
        <SectionHead>Before you run it</SectionHead>
        {setup.length === 0 ? (
          <Empty>No setup notes were stored.</Empty>
        ) : (
          <PlainList items={setup} />
        )}
      </Section>

      <Section className="col-narrow">
        <SectionHead>How to check it works</SectionHead>
        {plan.length === 0 ? (
          <Empty>No test plan was stored.</Empty>
        ) : (
          <PlainList items={plan} />
        )}
      </Section>

      {sourceSections.length > 0 ? (
        <Section className="col-narrow">
          <SectionHead end={<Num>{sourceSections.length}</Num>}>
            Sections this was built from
          </SectionHead>
          <Panel>
            <PanelBody>
              {sourceSections.map((section, index) => (
                <p key={getString(section, "id") || index}>
                  <b>{getString(section, "title", "Untitled section")}</b>{" "}
                  {getString(section, "content_preview", "No preview returned.")}
                </p>
              ))}
            </PanelBody>
          </Panel>
        </Section>
      ) : null}
    </>
  );
}

/* ------------------------------------------------------------------ */

function ArtifactBody({ artifact }: { artifact: WorkspaceSavedItemDetail }) {
  if (artifact.item_type === "comparison") {
    return <ComparisonView data={artifact.data} />;
  }

  if (artifact.item_type === "idea") {
    return <IdeaView data={artifact.data} />;
  }

  if (artifact.item_type === "implementation") {
    return <ImplementationView data={artifact.data} />;
  }

  return (
    <Section>
      <SectionHead>Stored payload</SectionHead>
      <p className="page-sub" style={{ marginBottom: "var(--space-lg)" }}>
        PaperTrail has no dedicated view for this saved type yet, so the stored
        payload is shown as it was written.
      </p>
      <CodeBlock path="payload.json" content={safeJson(artifact.data)} />
    </Section>
  );
}

function normalizeArtifactPayload(value: unknown): WorkspaceSavedItemDetail {
  const payload = isRecord(value) ? value : {};
  const data = isRecord(payload.data) ? payload.data : {};

  return {
    id: asString(payload.id),
    title: asString(payload.title, "Saved artifact"),
    item_type: asString(payload.item_type, "unknown"),
    paper_ids: asStringArray(payload.paper_ids),
    created_at: asString(payload.created_at),
    source_papers: Array.isArray(payload.source_papers)
      ? payload.source_papers.filter(isRecord).map((paper) => ({
          id: getString(paper, "id"),
          title: getString(paper, "title", "Untitled paper"),
          authors: getString(paper, "authors") || null,
          arxiv_url: getString(paper, "arxiv_url") || null,
          created_at: getString(paper, "created_at"),
        }))
      : [],
    data,
  };
}

export default function SavedArtifactDetailPage() {
  const params = useParams();
  const router = useRouter();
  const rawId = params?.id;
  const itemId = Array.isArray(rawId) ? rawId[0] : asString(rawId);

  const [artifact, setArtifact] = useState<WorkspaceSavedItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [renameTitle, setRenameTitle] = useState("");
  const [renameError, setRenameError] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [actionMessage, setActionMessage] = useState("");

  const loadArtifact = useCallback(async () => {
    if (!itemId) {
      setLoading(false);
      setError("Invalid saved artifact link.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/workspace/saved-items/${itemId}`);
      if (!res.ok) {
        if (res.status === 400) {
          throw new Error(
            await getApiErrorMessage(res, "Invalid saved artifact link."),
          );
        }
        if (res.status === 404) {
          throw new Error(
            await getApiErrorMessage(res, "Saved artifact not found."),
          );
        }
        throw new Error(
          await getApiErrorMessage(res, "Failed to load saved artifact."),
        );
      }

      const data = await res.json();
      setArtifact(normalizeArtifactPayload(data));
      setEditing(false);
      setRenameTitle("");
      setRenameError("");
      setDeleteConfirm(false);
      setDeleteError("");
      setActionMessage("");
    } catch (err) {
      setArtifact(null);
      setError(
        err instanceof Error ? err.message : "Failed to load saved artifact.",
      );
    } finally {
      setLoading(false);
    }
  }, [itemId]);

  const beginRename = () => {
    if (!artifact) {
      return;
    }

    setEditing(true);
    setRenameTitle(artifact.title);
    setRenameError("");
    setDeleteConfirm(false);
    setDeleteError("");
    setActionMessage("");
  };

  const cancelRename = () => {
    setEditing(false);
    setRenameTitle("");
    setRenameError("");
  };

  const renameArtifact = async () => {
    if (!artifact) {
      return;
    }

    const title = renameTitle.trim();
    if (!title) {
      setRenameError("Give this saved item a title before saving.");
      return;
    }

    setRenaming(true);
    setRenameError("");
    setActionMessage("");

    try {
      const res = await fetch(`${API_URL}/workspace/saved-items/${artifact.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });

      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to rename saved artifact."),
        );
      }

      const data = await res.json();
      setArtifact(normalizeArtifactPayload({ ...data, data: artifact.data }));
      cancelRename();
      setActionMessage("Renamed.");
    } catch (err) {
      setRenameError(
        err instanceof Error ? err.message : "Failed to rename saved artifact.",
      );
    } finally {
      setRenaming(false);
    }
  };

  const requestDelete = () => {
    setDeleteConfirm(true);
    setDeleteError("");
    setEditing(false);
    setRenameError("");
    setActionMessage("");
  };

  const deleteArtifact = async () => {
    if (!artifact) {
      return;
    }

    setDeleting(true);
    setDeleteError("");
    setActionMessage("");

    try {
      const res = await fetch(`${API_URL}/workspace/saved-items/${artifact.id}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        throw new Error(
          await getApiErrorMessage(res, "Failed to delete saved artifact."),
        );
      }

      router.push("/library");
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete saved artifact.",
      );
      setDeleting(false);
    }
  };

  useEffect(() => {
    loadArtifact();
  }, [loadArtifact]);

  const failureTitle = useMemo(() => {
    const normalized = error.toLowerCase();
    if (normalized.includes("not found")) {
      return "This saved item is not here";
    }
    if (normalized.includes("invalid saved")) {
      return "That link does not point at a saved item";
    }
    return "The saved item could not be loaded";
  }, [error]);

  if (loading) {
    return (
      <>
        <TopBar crumb={<b>Saved item</b>} />
        <Body>
          <PageSkeleton />
        </Body>
      </>
    );
  }

  if (error) {
    return (
      <>
        <TopBar crumb={<b>Saved item</b>} />
        <Body>
          <Blank
            kind="Cannot open"
            title={failureTitle}
            actions={
              <>
                <Button onClick={loadArtifact}>Try again</Button>
                <Button variant="ghost" onClick={() => router.push("/library")}>
                  Back to library
                </Button>
              </>
            }
          >
            {error}
          </Blank>
        </Body>
      </>
    );
  }

  if (!artifact) {
    return null;
  }

  return (
    <>
      <TopBar
        crumb={
          <>
            Library <span aria-hidden>/</span> <b>{artifact.title}</b>
          </>
        }
      />
      <Body>
        {editing ? (
          <form
            style={{ maxWidth: 560 }}
            onSubmit={(event) => {
              event.preventDefault();
              renameArtifact();
            }}
          >
            <Field label="Title" error={renameError || undefined}>
              <Input
                value={renameTitle}
                onChange={(event) => setRenameTitle(event.target.value)}
                disabled={renaming}
                invalid={Boolean(renameError)}
                maxLength={1000}
                autoFocus
              />
            </Field>
            <div style={{ display: "flex", gap: "var(--space-md)", marginTop: "var(--space-xl)" }}>
              <Button type="submit" disabled={renaming}>
                {renaming ? "Saving" : "Save"}
              </Button>
              <Button variant="ghost" onClick={cancelRename} disabled={renaming}>
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <PageHeader
            title={artifact.title}
            sub={
              <>
                <Tag>{formatType(artifact.item_type)}</Tag>{" "}
                Saved {formatDate(artifact.created_at)}
              </>
            }
            end={
              <>
                <Button variant="ghost" onClick={beginRename} disabled={deleting}>
                  Rename
                </Button>
                <Button
                  variant="danger"
                  onClick={requestDelete}
                  disabled={deleting || deleteConfirm}
                >
                  Delete
                </Button>
              </>
            }
          />
        )}

        {actionMessage ? (
          <div style={{ marginTop: "var(--space-lg)" }}>
            <Notice>{actionMessage}</Notice>
          </div>
        ) : null}

        {deleteConfirm ? (
          <Section>
            <Confirm
              title="Delete this saved item?"
              error={deleteError || undefined}
              actions={
                <>
                  <Button variant="danger" onClick={deleteArtifact} disabled={deleting}>
                    {deleting ? "Deleting" : "Delete"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setDeleteConfirm(false);
                      setDeleteError("");
                    }}
                    disabled={deleting}
                  >
                    Keep it
                  </Button>
                </>
              }
            >
              The source papers and the runs that produced this stay in your
              library. Only this saved copy goes.
            </Confirm>
          </Section>
        ) : null}

        {artifact.source_papers.length > 0 ? (
          <Section>
            <SectionHead>Source papers</SectionHead>
            <ChipRow>
              {artifact.source_papers.map((paper) => (
                <Chip key={paper.id} href={`/papers/${paper.id}`} title={paper.title}>
                  {paper.title}
                </Chip>
              ))}
            </ChipRow>
          </Section>
        ) : artifact.paper_ids.length > 0 ? (
          <Section>
            <SectionHead>Source papers</SectionHead>
            <Empty>
              This item names {artifact.paper_ids.length} source paper
              {artifact.paper_ids.length === 1 ? "" : "s"} that are no longer in
              your library.
            </Empty>
          </Section>
        ) : null}

        <ArtifactBody artifact={artifact} />
      </Body>
    </>
  );
}
