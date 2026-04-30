"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type JsonRecord = Record<string, unknown>;
type TabKey = "summary" | "algorithm" | "gaps" | "pseudocode" | "code" | "test";

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

const FEASIBILITY_STYLES: Record<string, string> = {
  low: "border-red-500/20 bg-red-500/10 text-red-500",
  medium: "border-amber-500/20 bg-amber-500/10 text-amber-600",
  high: "border-emerald-500/20 bg-emerald-500/10 text-emerald-600",
};

const SEVERITY_STYLES: Record<string, string> = {
  low: "border-[var(--border)] bg-[var(--card)] text-[var(--muted)]",
  medium: "border-amber-500/20 bg-amber-500/10 text-amber-600",
  high: "border-red-500/20 bg-red-500/10 text-red-500",
};

const IMPLEMENTATION_TABS: { key: TabKey; label: string }[] = [
  { key: "summary", label: "Summary" },
  { key: "algorithm", label: "Algorithm" },
  { key: "gaps", label: "Gaps" },
  { key: "pseudocode", label: "Pseudocode" },
  { key: "code", label: "Code" },
  { key: "test", label: "Test Plan" },
];

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

  return value
    .map((item) => asString(item))
    .filter((item) => item.length > 0);
}

function getStringArray(record: JsonRecord, key: string): string[] {
  return asStringArray(record[key]);
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Unknown date";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown date";
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

function typeClassName(itemType: string): string {
  if (itemType === "comparison") {
    return "border-blue-500/20 bg-blue-500/10 text-blue-600";
  }

  if (itemType === "idea") {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-600";
  }

  if (itemType === "implementation") {
    return "border-amber-500/20 bg-amber-500/10 text-amber-600";
  }

  return "border-[var(--border)] bg-[var(--card)] text-[var(--muted)]";
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

function LoadingState() {
  return (
    <div className="min-h-screen px-6 py-10">
      <main className="mx-auto w-full max-w-6xl space-y-8">
        <div className="space-y-3">
          <div className="h-5 w-28 rounded-lg bg-[var(--border)]" />
          <div className="h-10 w-full max-w-xl rounded-lg bg-[var(--border)]" />
          <div className="h-5 w-full max-w-2xl rounded-lg bg-[var(--border)]" />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={index}
              className="h-28 rounded-lg border border-[var(--border)] bg-[var(--card)]"
            />
          ))}
        </div>
        <div className="h-80 rounded-lg border border-[var(--border)] bg-[var(--card)]" />
      </main>
    </div>
  );
}

function ErrorState({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="min-h-screen px-6 py-10">
      <main className="mx-auto flex min-h-[60vh] w-full max-w-3xl items-center">
        <div className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-6">
          <p className="text-sm font-medium text-red-500">Saved artifact unavailable</p>
          <h1 className="mt-2 text-2xl font-semibold">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{message}</p>
          <div className="mt-5 flex flex-wrap gap-3 text-sm">
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg bg-[var(--primary)] px-4 py-2 font-medium text-white transition-colors hover:bg-[var(--primary-hover)]"
            >
              Retry
            </button>
            <Link
              href="/dashboard"
              className="rounded-lg border border-[var(--border)] px-4 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)]"
            >
              Back to Workspace
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

function ArtifactHeader({
  artifact,
  actionMessage,
  editing,
  renameTitle,
  renameError,
  renaming,
  deleteConfirm,
  deleteError,
  deleting,
  onBeginRename,
  onCancelRename,
  onRenameTitleChange,
  onRename,
  onRequestDelete,
  onCancelDelete,
  onDelete,
}: {
  artifact: WorkspaceSavedItemDetail;
  actionMessage: string;
  editing: boolean;
  renameTitle: string;
  renameError: string;
  renaming: boolean;
  deleteConfirm: boolean;
  deleteError: string;
  deleting: boolean;
  onBeginRename: () => void;
  onCancelRename: () => void;
  onRenameTitleChange: (title: string) => void;
  onRename: () => void;
  onRequestDelete: () => void;
  onCancelDelete: () => void;
  onDelete: () => void;
}) {
  return (
    <header className="space-y-5">
      <Link
        href="/dashboard"
        className="text-sm font-medium text-[var(--primary)] transition-colors hover:text-[var(--primary-hover)]"
      >
        &larr; Workspace
      </Link>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2.5 py-1 text-xs ${typeClassName(
                artifact.item_type,
              )}`}
            >
              {formatType(artifact.item_type)}
            </span>
            <span className="text-sm text-[var(--muted)]">
              Saved {formatDate(artifact.created_at)}
            </span>
          </div>
          {editing ? (
            <form
              className="mt-4 max-w-2xl space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                onRename();
              }}
            >
              <label htmlFor="saved-artifact-title" className="sr-only">
                Saved artifact title
              </label>
              <input
                id="saved-artifact-title"
                value={renameTitle}
                onChange={(event) => onRenameTitleChange(event.target.value)}
                disabled={renaming}
                maxLength={1000}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-base outline-none transition-colors focus:border-[var(--primary)]"
              />
              {renameError && (
                <p className="text-sm text-red-500">{renameError}</p>
              )}
              <div className="flex flex-wrap gap-2 text-sm">
                <button
                  type="submit"
                  disabled={renaming}
                  className="rounded-lg bg-[var(--primary)] px-3 py-2 font-medium text-white transition-colors hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {renaming ? "Saving..." : "Save"}
                </button>
                <button
                  type="button"
                  onClick={onCancelRename}
                  disabled={renaming}
                  className="rounded-lg border border-[var(--border)] px-3 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <h1 className="mt-3 text-4xl font-bold tracking-tight">
              {artifact.title}
            </h1>
          )}
          {actionMessage && (
            <p className="mt-3 text-sm font-medium text-emerald-600">
              {actionMessage}
            </p>
          )}
        </div>
        {!editing && (
          <div className="flex shrink-0 flex-wrap gap-2 text-sm">
            <button
              type="button"
              onClick={onBeginRename}
              disabled={deleting}
              className="rounded-lg border border-[var(--border)] px-3 py-2 font-medium transition-colors hover:border-[var(--primary)]/40 hover:text-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              Rename
            </button>
            <button
              type="button"
              onClick={onRequestDelete}
              disabled={deleting}
              className="rounded-lg border border-red-500/30 px-3 py-2 font-medium text-red-500 transition-colors hover:border-red-500 hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Delete
            </button>
          </div>
        )}
      </div>

      {deleteConfirm && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <p className="text-sm font-medium text-red-600">
            Delete this saved artifact?
          </p>
          <p className="mt-1 text-sm leading-6 text-red-600">
            Source papers and generated workflow history will stay in the
            workspace.
          </p>
          {deleteError && (
            <p className="mt-2 text-sm text-red-600">{deleteError}</p>
          )}
          <div className="mt-3 flex flex-wrap gap-2 text-sm">
            <button
              type="button"
              onClick={onDelete}
              disabled={deleting}
              className="rounded-lg bg-red-600 px-3 py-2 font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {deleting ? "Deleting..." : "Delete"}
            </button>
            <button
              type="button"
              onClick={onCancelDelete}
              disabled={deleting}
              className="rounded-lg border border-red-500/30 px-3 py-2 font-medium text-red-600 transition-colors hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="text-lg font-semibold">Source Papers</h2>
        {artifact.source_papers.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {artifact.source_papers.map((paper) => (
              <Link
                key={paper.id}
                href={`/papers/${paper.id}`}
                className="max-w-full rounded-full border border-[var(--border)] px-3 py-1.5 text-sm transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)]"
              >
                <span className="line-clamp-1">{paper.title}</span>
              </Link>
            ))}
          </div>
        ) : artifact.paper_ids.length > 0 ? (
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            Source paper records are unavailable for this saved artifact.
          </p>
        ) : (
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            This saved artifact does not reference a local source paper.
          </p>
        )}
      </section>
    </header>
  );
}

function WarningList({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <section className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-5">
      <h2 className="text-lg font-semibold text-amber-700">Warnings</h2>
      <ul className="mt-4 space-y-2 text-sm text-amber-700">
        {warnings.map((warning, index) => (
          <li
            key={`${warning}-${index}`}
            className="rounded-lg bg-[var(--background)]/70 px-4 py-3 leading-relaxed"
          >
            {warning}
          </li>
        ))}
      </ul>
    </section>
  );
}

function EmptyBlock({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--border)] p-5 text-sm text-[var(--muted)]">
      {message}
    </div>
  );
}

function ListBlock({ title, items }: { title?: string; items: string[] }) {
  return (
    <div className={title ? "" : "mt-4"}>
      {title && <h3 className="text-sm font-semibold">{title}</h3>}
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-[var(--muted)]">None returned.</p>
      ) : (
        <ul className="mt-2 space-y-2 text-sm">
          {items.map((item, index) => (
            <li
              key={`${item}-${index}`}
              className="rounded-lg bg-[var(--background)] px-3 py-2 leading-6 text-[var(--muted)]"
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PayloadPreview({ data }: { data: JsonRecord }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
      <h2 className="text-lg font-semibold">Stored Payload</h2>
      <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
        This is the read-only historical payload stored for the artifact.
      </p>
      <pre className="mt-4 max-h-[560px] overflow-auto rounded-lg bg-[var(--background)] p-4 text-sm leading-6">
        <code>{safeJson(data)}</code>
      </pre>
    </section>
  );
}

function SelectedPaperCards({ papers }: { papers: JsonRecord[] }) {
  if (papers.length === 0) {
    return <EmptyBlock message="No selected paper metadata was returned." />;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {papers.map((paper, index) => {
        const id = getString(paper, "id");
        const title = getString(paper, "title", "Untitled paper");
        const authors = getString(paper, "authors");

        return (
          <article
            key={id || `${title}-${index}`}
            className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h3 className="line-clamp-2 text-lg font-semibold">{title}</h3>
                {authors && (
                  <p className="mt-1 line-clamp-2 text-sm text-[var(--muted)]">
                    {authors}
                  </p>
                )}
              </div>
              {id && (
                <Link
                  href={`/papers/${id}`}
                  className="shrink-0 text-sm text-[var(--primary)] hover:underline"
                >
                  Open
                </Link>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function ComparisonRenderer({ data }: { data: JsonRecord }) {
  const selectedPapers = getRecordArray(data, "selected_papers");
  const profiles = getRecordArray(data, "normalized_profiles");
  const table = getRecord(data, "comparison_table");
  const columns = getRecordArray(table, "columns");
  const rows = getRecordArray(table, "rows");
  const warnings = getStringArray(data, "warnings");
  const narrativeSummary = getString(data, "narrative_summary");

  return (
    <section className="space-y-6">
      <SelectedPaperCards papers={selectedPapers} />
      <WarningList warnings={warnings} />

      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="text-lg font-semibold">Narrative Summary</h2>
        {narrativeSummary ? (
          <div className="mt-4 whitespace-pre-wrap text-sm leading-7">
            {narrativeSummary}
          </div>
        ) : (
          <p className="mt-3 text-sm text-[var(--muted)]">
            No narrative summary was stored.
          </p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Paper Profiles</h2>
        {profiles.length === 0 ? (
          <EmptyBlock message="No normalized paper profiles were stored." />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {profiles.map((profile, index) => (
              <ProfileCard
                key={getString(profile, "paper_id") || index}
                profile={profile}
              />
            ))}
          </div>
        )}
      </section>

      <section className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <h2 className="text-lg font-semibold">Comparison Table</h2>
        </div>
        {columns.length === 0 || rows.length === 0 ? (
          <div className="p-5">
            <EmptyBlock message="No comparison table was stored." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-[960px] w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  {columns.map((column, index) => (
                    <th
                      key={getString(column, "key") || index}
                      className={`px-5 py-4 text-left align-top font-semibold ${
                        index === 0
                          ? "sticky left-0 z-10 min-w-52 bg-[var(--card)]"
                          : "min-w-64"
                      }`}
                    >
                      {getString(column, "label", `Column ${index + 1}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rowIndex) => {
                  const values = getStringArray(row, "values");
                  return (
                    <tr
                      key={getString(row, "key") || rowIndex}
                      className="border-b border-[var(--border)] last:border-b-0"
                    >
                      <th className="sticky left-0 z-10 min-w-52 bg-[var(--card)] px-5 py-4 text-left align-top font-medium">
                        {getString(row, "label", `Row ${rowIndex + 1}`)}
                      </th>
                      {values.map((value, valueIndex) => (
                        <td
                          key={`${rowIndex}-${valueIndex}`}
                          className="min-w-64 px-5 py-4 align-top leading-6 text-[var(--foreground)]/90"
                        >
                          {value}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}

function ProfileCard({ profile }: { profile: JsonRecord }) {
  const fields = [
    ["Problem", "problem"],
    ["Method", "method"],
    ["Dataset or Eval Setup", "dataset_or_eval_setup"],
    ["Key Results", "key_results"],
    ["Strengths", "strengths"],
    ["Weaknesses", "weaknesses"],
  ];
  const evidenceNotes = getRecord(profile, "evidence_notes");
  const warnings = getStringArray(profile, "warnings");

  return (
    <article className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
      <h3 className="text-lg font-semibold">
        {getString(profile, "title", "Untitled profile")}
      </h3>
      {getString(profile, "authors") && (
        <p className="mt-1 text-sm text-[var(--muted)]">
          {getString(profile, "authors")}
        </p>
      )}
      <div className="mt-4 space-y-4 text-sm leading-6">
        {fields.map(([label, key]) => (
          <div key={key}>
            <h4 className="font-semibold">{label}</h4>
            <p className="mt-1 text-[var(--foreground)]/90">
              {getString(profile, key, "Not returned.")}
            </p>
          </div>
        ))}
        {Object.keys(evidenceNotes).length > 0 && (
          <div>
            <h4 className="font-semibold">Evidence Notes</h4>
            <div className="mt-2 space-y-3">
              {Object.entries(evidenceNotes).map(([key, value]) => (
                <ListBlock
                  key={key}
                  title={key.replace(/_/g, " ")}
                  items={asStringArray(value)}
                />
              ))}
            </div>
          </div>
        )}
        {warnings.length > 0 && (
          <ListBlock title="Profile Warnings" items={warnings} />
        )}
      </div>
    </article>
  );
}

function IdeaRenderer({ data }: { data: JsonRecord }) {
  const selectedPapers = getRecordArray(data, "selected_papers");
  const sourceTopic = getString(data, "source_topic");
  const ideas = getRecordArray(data, "ideas");
  const warnings = getStringArray(data, "warnings");

  return (
    <section className="space-y-6">
      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="text-lg font-semibold">Source Basis</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {selectedPapers.map((paper, index) => {
            const id = getString(paper, "id");
            return id ? (
              <Link
                key={id}
                href={`/papers/${id}`}
                className="max-w-full rounded-full border border-[var(--border)] px-3 py-1.5 text-sm transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)]"
              >
                <span className="line-clamp-1">
                  {getString(paper, "title", "Untitled paper")}
                </span>
              </Link>
            ) : (
              <span
                key={`${getString(paper, "title")}-${index}`}
                className="max-w-full rounded-full border border-[var(--border)] px-3 py-1.5 text-sm"
              >
                <span className="line-clamp-1">
                  {getString(paper, "title", "Untitled paper")}
                </span>
              </span>
            );
          })}
          {sourceTopic && (
            <span className="max-w-full rounded-full bg-[var(--primary)]/10 px-3 py-1.5 text-sm text-[var(--primary)]">
              <span className="line-clamp-1">{sourceTopic}</span>
            </span>
          )}
          {selectedPapers.length === 0 && !sourceTopic && (
            <span className="text-sm text-[var(--muted)]">
              No source basis was stored.
            </span>
          )}
        </div>
      </section>

      <WarningList warnings={warnings} />

      {ideas.length === 0 ? (
        <EmptyBlock message="No generated ideas were stored." />
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          {ideas.map((idea, index) => (
            <IdeaCard key={`${getString(idea, "title")}-${index}`} idea={idea} />
          ))}
        </div>
      )}
    </section>
  );
}

function IdeaCard({ idea }: { idea: JsonRecord }) {
  const transformationType = getString(idea, "transformation_type");
  const feasibility = getString(idea, "feasibility");
  const critique = getString(idea, "critique");
  const score = getString(idea, "score");
  const warnings = getStringArray(idea, "warnings");

  return (
    <article className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
      <div className="flex flex-wrap gap-2">
        {transformationType && (
          <span className="rounded-full bg-[var(--primary)]/10 px-2.5 py-1 text-xs font-medium text-[var(--primary)]">
            {TRANSFORMATION_LABELS[transformationType] || transformationType}
          </span>
        )}
        {feasibility && (
          <span
            className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
              FEASIBILITY_STYLES[feasibility] ||
              "border-[var(--border)] text-[var(--muted)]"
            }`}
          >
            {feasibility} feasibility
          </span>
        )}
        {score && (
          <span className="rounded-full border border-[var(--border)] px-2.5 py-1 text-xs font-medium text-[var(--muted)]">
            Score {score}
          </span>
        )}
      </div>
      <h2 className="mt-3 text-xl font-semibold leading-snug">
        {getString(idea, "title", "Untitled idea")}
      </h2>
      <div className="mt-4 space-y-4 text-sm leading-6">
        <TextSection title="Description" value={getString(idea, "description")} />
        <TextSection
          title="Why Interesting"
          value={getString(idea, "why_interesting")}
        />
        {critique && <TextSection title="Critique" value={critique} />}
        <ListBlock
          title="Evidence Basis"
          items={getStringArray(idea, "evidence_basis")}
        />
        <ListBlock
          title="Risks or Unknowns"
          items={getStringArray(idea, "risks_or_unknowns")}
        />
        {warnings.length > 0 && <ListBlock title="Warnings" items={warnings} />}
      </div>
    </article>
  );
}

function TextSection({ title, value }: { title: string; value: string }) {
  return (
    <div>
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-1 text-[var(--foreground)]/90">
        {value || "Not returned."}
      </p>
    </div>
  );
}

function ImplementationRenderer({ data }: { data: JsonRecord }) {
  const [activeTab, setActiveTab] = useState<TabKey>("summary");
  const [copyStatus, setCopyStatus] = useState<Record<string, string>>({});
  const paper = getRecord(data, "paper");
  const warnings = getStringArray(data, "warnings");

  const handleCopy = async (path: string, content: string) => {
    try {
      await copyTextToClipboard(content);
      setCopyStatus((current) => ({ ...current, [path]: "Copied" }));
    } catch {
      setCopyStatus((current) => ({ ...current, [path]: "Copy failed" }));
    }
  };

  return (
    <section className="space-y-6">
      {Object.keys(paper).length > 0 && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
          <h2 className="text-lg font-semibold">
            {getString(paper, "title", "Source paper")}
          </h2>
          {getString(paper, "authors") && (
            <p className="mt-1 text-sm text-[var(--muted)]">
              {getString(paper, "authors")}
            </p>
          )}
        </section>
      )}

      <WarningList warnings={warnings} />

      <div className="overflow-x-auto border-b border-[var(--border)]">
        <div className="flex min-w-max gap-2">
          {IMPLEMENTATION_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--muted)] hover:text-[var(--foreground)]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "summary" && <ImplementationSummary data={data} />}
      {activeTab === "algorithm" && <ImplementationAlgorithm data={data} />}
      {activeTab === "gaps" && <ImplementationGaps data={data} />}
      {activeTab === "pseudocode" && <ImplementationPseudocode data={data} />}
      {activeTab === "code" && (
        <ImplementationCode
          data={data}
          copyStatus={copyStatus}
          onCopy={handleCopy}
        />
      )}
      {activeTab === "test" && <ImplementationTestPlan data={data} />}
    </section>
  );
}

function ImplementationSummary({ data }: { data: JsonRecord }) {
  const sourceSections = getRecordArray(data, "source_sections");

  return (
    <section className="space-y-5">
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="text-lg font-semibold">Summary</h2>
        <p className="mt-3 leading-7">
          {getString(data, "implementation_summary", "No implementation summary was stored.")}
        </p>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="text-lg font-semibold">Source Sections</h2>
        {sourceSections.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--muted)]">
            No source sections were returned.
          </p>
        ) : (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {sourceSections.map((section, index) => (
              <article
                key={getString(section, "id") || index}
                className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold">
                    {getString(section, "title", "Untitled section")}
                  </h3>
                  <span className="text-xs text-[var(--muted)]">
                    #{getString(section, "section_order", String(index + 1))}
                  </span>
                </div>
                <p className="mt-2 line-clamp-5 text-sm leading-6 text-[var(--muted)]">
                  {getString(section, "content_preview", "No preview returned.")}
                </p>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function ImplementationAlgorithm({ data }: { data: JsonRecord }) {
  const steps = getRecordArray(data, "algorithm_steps");

  if (steps.length === 0) {
    return <EmptyBlock message="No grounded algorithm steps were stored." />;
  }

  return (
    <section className="space-y-4">
      {steps.map((step, index) => (
        <article
          key={`${getString(step, "order")}-${getString(step, "title")}-${index}`}
          className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5"
        >
          <span className="text-xs font-semibold uppercase text-[var(--primary)]">
            Step {getString(step, "order", String(index + 1))}
          </span>
          <h2 className="mt-1 text-xl font-semibold">
            {getString(step, "title", "Untitled step")}
          </h2>
          <p className="mt-3 leading-7">
            {getString(step, "description", "No description returned.")}
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <ListBlock title="Inputs" items={getStringArray(step, "inputs")} />
            <ListBlock title="Outputs" items={getStringArray(step, "outputs")} />
            <ListBlock title="Evidence" items={getStringArray(step, "evidence")} />
          </div>
        </article>
      ))}
    </section>
  );
}

function ImplementationGaps({ data }: { data: JsonRecord }) {
  const gaps = getRecordArray(data, "assumptions_and_gaps");

  if (gaps.length === 0) {
    return <EmptyBlock message="No assumptions or gaps were stored." />;
  }

  return (
    <section className="grid gap-4 lg:grid-cols-2">
      {gaps.map((gap, index) => {
        const severity = getString(gap, "severity");
        return (
          <article
            key={`${getString(gap, "category")}-${index}`}
            className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-[var(--primary)]/10 px-2.5 py-1 text-xs font-medium text-[var(--primary)]">
                {getString(gap, "category", "uncategorized").replace(/_/g, " ")}
              </span>
              {severity && (
                <span
                  className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                    SEVERITY_STYLES[severity] ||
                    "border-[var(--border)] text-[var(--muted)]"
                  }`}
                >
                  {severity} severity
                </span>
              )}
            </div>
            <p className="mt-4 leading-7">
              {getString(gap, "description", "No description returned.")}
            </p>
            <ListBlock title="Evidence" items={getStringArray(gap, "evidence")} />
          </article>
        );
      })}
    </section>
  );
}

function ImplementationPseudocode({ data }: { data: JsonRecord }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
      <h2 className="text-lg font-semibold">Pseudocode</h2>
      <pre className="mt-4 overflow-x-auto rounded-lg bg-[var(--background)] p-4 text-sm leading-6">
        <code>{getString(data, "pseudocode", "No pseudocode was stored.")}</code>
      </pre>
    </section>
  );
}

function ImplementationCode({
  data,
  copyStatus,
  onCopy,
}: {
  data: JsonRecord;
  copyStatus: Record<string, string>;
  onCopy: (path: string, content: string) => void;
}) {
  const files = getRecordArray(data, "starter_code");

  if (files.length === 0) {
    return <EmptyBlock message="No starter code files were stored." />;
  }

  return (
    <section className="space-y-5">
      {files.map((file, index) => {
        const path = getString(file, "path", `file-${index + 1}`);
        const content = getString(file, "content", "No content returned.");
        return (
          <article
            key={`${path}-${index}`}
            className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]"
          >
            <div className="flex flex-col gap-3 border-b border-[var(--border)] px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h2 className="font-semibold">{path}</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  {getString(file, "purpose", "No purpose returned.")}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                {copyStatus[path] && (
                  <span className="text-xs text-[var(--muted)]">
                    {copyStatus[path]}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => onCopy(path, content)}
                  className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-medium transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)]"
                >
                  Copy
                </button>
              </div>
            </div>
            <pre className="overflow-x-auto bg-[var(--background)] p-5 text-sm leading-6">
              <code>{content}</code>
            </pre>
          </article>
        );
      })}
    </section>
  );
}

function ImplementationTestPlan({ data }: { data: JsonRecord }) {
  return (
    <section className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="text-lg font-semibold">Setup Notes</h2>
        <ListBlock items={getStringArray(data, "setup_notes")} />
      </div>
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="text-lg font-semibold">Test Plan</h2>
        <ListBlock items={getStringArray(data, "test_plan")} />
      </div>
    </section>
  );
}

function ArtifactRenderer({ artifact }: { artifact: WorkspaceSavedItemDetail }) {
  if (artifact.item_type === "comparison") {
    return <ComparisonRenderer data={artifact.data} />;
  }

  if (artifact.item_type === "idea") {
    return <IdeaRenderer data={artifact.data} />;
  }

  if (artifact.item_type === "implementation") {
    return <ImplementationRenderer data={artifact.data} />;
  }

  return (
    <section className="space-y-6">
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="text-lg font-semibold">Unsupported Saved Type</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          Papertrail does not have a specialized renderer for this saved artifact
          type yet, so the stored payload is shown as read-only JSON.
        </p>
      </div>
      <PayloadPreview data={artifact.data} />
    </section>
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
      setRenameError("Saved item title is required.");
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
      setActionMessage("Saved artifact renamed.");
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

  const cancelDelete = () => {
    setDeleteConfirm(false);
    setDeleteError("");
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

      router.push("/dashboard");
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

  const title = useMemo(() => {
    const normalizedError = error.toLowerCase();
    if (normalizedError.includes("not found")) {
      return "Saved artifact not found";
    }
    if (normalizedError.includes("invalid saved")) {
      return "Invalid saved artifact link";
    }
    return "Could not load saved artifact";
  }, [error]);

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState title={title} message={error} onRetry={loadArtifact} />;
  }

  if (!artifact) {
    return null;
  }

  return (
    <div className="min-h-screen px-6 py-10">
      <main className="mx-auto w-full max-w-6xl space-y-8">
        <ArtifactHeader
          artifact={artifact}
          actionMessage={actionMessage}
          editing={editing}
          renameTitle={renameTitle}
          renameError={renameError}
          renaming={renaming}
          deleteConfirm={deleteConfirm}
          deleteError={deleteError}
          deleting={deleting}
          onBeginRename={beginRename}
          onCancelRename={cancelRename}
          onRenameTitleChange={setRenameTitle}
          onRename={renameArtifact}
          onRequestDelete={requestDelete}
          onCancelDelete={cancelDelete}
          onDelete={deleteArtifact}
        />
        <ArtifactRenderer artifact={artifact} />
      </main>
    </div>
  );
}
