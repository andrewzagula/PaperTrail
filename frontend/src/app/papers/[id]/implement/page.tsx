"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type TargetFramework = "pytorch" | "generic-python";
type GapSeverity = "low" | "medium" | "high";
type TabKey = "summary" | "algorithm" | "gaps" | "pseudocode" | "code" | "test";

interface Paper {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
}

interface ImplementationPaperResponse {
  id: string;
  title: string;
  authors: string | null;
  arxiv_url: string | null;
  created_at: string;
}

interface ImplementationSourceSectionResponse {
  id: string;
  title: string;
  section_order: number;
  content_preview: string;
}

interface AlgorithmStepResponse {
  order: number;
  title: string;
  description: string;
  inputs: string[];
  outputs: string[];
  evidence: string[];
}

interface AssumptionGapResponse {
  category: string;
  description: string;
  severity: GapSeverity;
  evidence: string[];
}

interface StarterCodeFileResponse {
  path: string;
  language: string;
  purpose: string;
  content: string;
}

interface ImplementationResponse {
  paper: ImplementationPaperResponse;
  source_sections: ImplementationSourceSectionResponse[];
  implementation_summary: string;
  algorithm_steps: AlgorithmStepResponse[];
  assumptions_and_gaps: AssumptionGapResponse[];
  pseudocode: string;
  starter_code: StarterCodeFileResponse[];
  setup_notes: string[];
  test_plan: string[];
  warnings: string[];
}

interface SaveImplementationResponse {
  id: string;
  title: string;
  item_type: "implementation";
  paper_ids: string[];
  created_at: string;
}

const TABS: { key: TabKey; label: string }[] = [
  { key: "summary", label: "Summary" },
  { key: "algorithm", label: "Algorithm" },
  { key: "gaps", label: "Gaps" },
  { key: "pseudocode", label: "Pseudocode" },
  { key: "code", label: "Code" },
  { key: "test", label: "Test Plan" },
];

const FRAMEWORK_LABELS: Record<TargetFramework, string> = {
  pytorch: "PyTorch",
  "generic-python": "Generic Python",
};

const SEVERITY_STYLES: Record<GapSeverity, string> = {
  low: "border-[var(--border)] bg-[var(--card)] text-[var(--muted)]",
  medium: "border-amber-500/20 bg-amber-500/10 text-amber-600",
  high: "border-red-500/20 bg-red-500/10 text-red-500",
};

function createDefaultImplementationTitle(result: ImplementationResponse): string {
  return `Implementation: ${result.paper.title}`;
}

function createSaveKey(result: ImplementationResponse, title: string): string {
  return `${result.paper.id}::${title}::${result.starter_code
    .map((file) => file.path)
    .join(",")}`;
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

export default function PaperImplementationPage() {
  const params = useParams();
  const paperId = params.id as string;

  const [paper, setPaper] = useState<Paper | null>(null);
  const [paperLoading, setPaperLoading] = useState(true);
  const [paperError, setPaperError] = useState("");
  const [focus, setFocus] = useState("");
  const [targetFramework, setTargetFramework] =
    useState<TargetFramework>("pytorch");
  const [implementationResult, setImplementationResult] =
    useState<ImplementationResponse | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("summary");
  const [generationLoading, setGenerationLoading] = useState(false);
  const [generationError, setGenerationError] = useState("");
  const [saveTitle, setSaveTitle] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState("");
  const [lastSavedKey, setLastSavedKey] = useState("");
  const [copyStatus, setCopyStatus] = useState<Record<string, string>>({});

  useEffect(() => {
    async function loadPaper() {
      setPaperLoading(true);
      setPaperError("");

      try {
        const res = await fetch(`${API_URL}/papers/${paperId}`);
        if (!res.ok) {
          throw new Error("Paper not found.");
        }

        const data: Paper = await res.json();
        setPaper(data);
      } catch (err) {
        setPaperError(err instanceof Error ? err.message : "Failed to load paper.");
      } finally {
        setPaperLoading(false);
      }
    }

    loadPaper();
  }, [paperId]);

  const generatedCodeFiles = implementationResult?.starter_code ?? [];
  const generationDisabled = generationLoading || paperLoading || Boolean(paperError);

  const generatedCounts = useMemo(() => {
    if (!implementationResult) {
      return null;
    }

    return {
      steps: implementationResult.algorithm_steps.length,
      gaps: implementationResult.assumptions_and_gaps.length,
      files: implementationResult.starter_code.length,
      warnings: implementationResult.warnings.length,
    };
  }, [implementationResult]);

  const clearResultState = () => {
    setImplementationResult(null);
    setGenerationError("");
    setSaveTitle("");
    setSaveLoading(false);
    setSaveError("");
    setSaveSuccess("");
    setLastSavedKey("");
    setCopyStatus({});
    setActiveTab("summary");
  };

  const handleFocusChange = (value: string) => {
    setFocus(value);
    if (implementationResult || generationError || saveSuccess || saveError) {
      clearResultState();
    }
  };

  const handleFrameworkChange = (value: TargetFramework) => {
    setTargetFramework(value);
    if (implementationResult || generationError || saveSuccess || saveError) {
      clearResultState();
    }
  };

  const handleGenerateImplementation = async () => {
    setGenerationLoading(true);
    setGenerationError("");
    setSaveError("");
    setSaveSuccess("");
    setCopyStatus({});

    try {
      const normalizedFocus = focus.trim();
      const res = await fetch(`${API_URL}/papers/${paperId}/implement`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          focus: normalizedFocus || null,
          target_language: "python",
          target_framework: targetFramework,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Implementation generation failed.");
      }

      const data: ImplementationResponse = await res.json();
      setImplementationResult(data);
      setSaveTitle(createDefaultImplementationTitle(data));
      setLastSavedKey("");
      setActiveTab("summary");
    } catch (err) {
      setImplementationResult(null);
      setSaveTitle("");
      setGenerationError(
        err instanceof Error ? err.message : "Implementation generation failed.",
      );
    } finally {
      setGenerationLoading(false);
    }
  };

  const handleSaveImplementation = async () => {
    if (!implementationResult) {
      return;
    }

    const normalizedTitle = saveTitle.trim();
    if (!normalizedTitle) {
      setSaveError("Implementation title is required.");
      setSaveSuccess("");
      return;
    }

    const saveKey = createSaveKey(implementationResult, normalizedTitle);
    if (saveKey === lastSavedKey) {
      setSaveError("This implementation result is already saved with that title.");
      setSaveSuccess("");
      return;
    }

    setSaveLoading(true);
    setSaveError("");
    setSaveSuccess("");

    try {
      const res = await fetch(`${API_URL}/papers/${paperId}/implement/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: normalizedTitle,
          implementation: implementationResult,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to save implementation.");
      }

      const data: SaveImplementationResponse = await res.json();
      setSaveTitle(data.title);
      setSaveSuccess(`Saved implementation as "${data.title}".`);
      setLastSavedKey(saveKey);
    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to save implementation.",
      );
    } finally {
      setSaveLoading(false);
    }
  };

  const handleCopyFile = async (file: StarterCodeFileResponse) => {
    setCopyStatus((current) => ({ ...current, [file.path]: "Copying..." }));

    try {
      await copyTextToClipboard(file.content);
      setCopyStatus((current) => ({ ...current, [file.path]: "Copied" }));
      window.setTimeout(() => {
        setCopyStatus((current) => {
          const next = { ...current };
          delete next[file.path];
          return next;
        });
      }, 1600);
    } catch {
      setCopyStatus((current) => ({ ...current, [file.path]: "Copy failed" }));
    }
  };

  if (paperLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
      </div>
    );
  }

  if (paperError || !paper) {
    return (
      <div className="mx-auto min-h-screen max-w-3xl px-6 py-10">
        <a
          href="/"
          className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
        >
          &larr; Home
        </a>
        <div className="mt-8 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
          {paperError || "Paper not found."}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-6 py-10">
      <main className="mx-auto max-w-7xl space-y-8">
        <div className="border-b border-[var(--border)] pb-8">
          <a
            href={`/papers/${paper.id}`}
            className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
          >
            &larr; Paper
          </a>
          <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="min-w-0">
              <h1 className="text-4xl font-bold tracking-tight">
                Build Implementation
              </h1>
              <h2 className="mt-3 max-w-4xl text-xl font-semibold leading-snug">
                {paper.title}
              </h2>
              {paper.authors && (
                <p className="mt-2 text-sm text-[var(--muted)] line-clamp-2">
                  {paper.authors}
                </p>
              )}
            </div>

            {generatedCounts && (
              <div className="flex flex-wrap gap-2 text-sm">
                <span className="rounded-full border border-[var(--border)] px-3 py-1.5 text-[var(--muted)]">
                  {generatedCounts.steps} steps
                </span>
                <span className="rounded-full border border-[var(--border)] px-3 py-1.5 text-[var(--muted)]">
                  {generatedCounts.gaps} gaps
                </span>
                <span className="rounded-full border border-[var(--border)] px-3 py-1.5 text-[var(--muted)]">
                  {generatedCounts.files} files
                </span>
                <span className="rounded-full border border-[var(--border)] px-3 py-1.5 text-[var(--muted)]">
                  {generatedCounts.warnings} warnings
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
          <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
            <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
              <h2 className="text-lg font-semibold">Generation</h2>

              <label
                htmlFor="implementation-focus"
                className="mt-5 block text-sm font-medium"
              >
                Focus
              </label>
              <textarea
                id="implementation-focus"
                value={focus}
                maxLength={1000}
                onChange={(event) => handleFocusChange(event.target.value)}
                placeholder="Optional: training loop, inference only, loss function"
                rows={5}
                disabled={generationLoading}
                className="mt-2 w-full resize-y rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-sm leading-6 outline-none transition-colors placeholder:text-[var(--muted)] focus:border-[var(--primary)] disabled:opacity-60"
              />

              <div className="mt-5">
                <h3 className="text-sm font-medium">Framework</h3>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {(Object.keys(FRAMEWORK_LABELS) as TargetFramework[]).map(
                    (framework) => (
                      <button
                        key={framework}
                        onClick={() => handleFrameworkChange(framework)}
                        disabled={generationLoading}
                        className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                          targetFramework === framework
                            ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                            : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
                        }`}
                      >
                        {FRAMEWORK_LABELS[framework]}
                      </button>
                    ),
                  )}
                </div>
              </div>

              {generationError && (
                <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
                  {generationError}
                </div>
              )}

              <button
                onClick={handleGenerateImplementation}
                disabled={generationDisabled}
                className="mt-5 w-full rounded-lg bg-[var(--primary)] px-4 py-3 font-medium text-white transition-colors hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {generationLoading ? "Generating..." : "Generate Implementation"}
              </button>
            </section>

            {implementationResult && (
              <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                <h2 className="text-lg font-semibold">Save</h2>
                <input
                  type="text"
                  value={saveTitle}
                  maxLength={1000}
                  disabled={saveLoading}
                  onChange={(event) => {
                    setSaveTitle(event.target.value);
                    setSaveError("");
                    setSaveSuccess("");
                  }}
                  placeholder="Implementation title"
                  className="mt-4 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm outline-none transition-colors focus:border-[var(--primary)] disabled:opacity-60"
                />
                <button
                  onClick={handleSaveImplementation}
                  disabled={saveLoading}
                  className="mt-3 w-full rounded-lg border border-[var(--border)] px-4 py-2.5 text-sm font-medium transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saveLoading ? "Saving..." : "Save Implementation"}
                </button>
                {saveError && <p className="mt-3 text-sm text-red-500">{saveError}</p>}
                {saveSuccess && (
                  <p className="mt-3 text-sm text-[var(--primary)]">{saveSuccess}</p>
                )}
              </section>
            )}
          </aside>

          <section className="min-w-0 space-y-6">
            {!implementationResult ? (
              <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] px-6 py-14 text-center">
                <h2 className="text-xl font-semibold">No implementation generated</h2>
                <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
                  Generate a grounded scaffold from the paper method, gaps, pseudocode,
                  starter files, setup notes, and test checks.
                </p>
              </div>
            ) : (
              <>
                {implementationResult.warnings.length > 0 && (
                  <section className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-5">
                    <h2 className="text-lg font-semibold text-amber-700">Warnings</h2>
                    <ul className="mt-4 space-y-2 text-sm text-amber-700">
                      {implementationResult.warnings.map((warning) => (
                        <li
                          key={warning}
                          className="rounded-lg bg-[var(--background)]/70 px-4 py-3 leading-relaxed"
                        >
                          {warning}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                <div className="overflow-x-auto border-b border-[var(--border)]">
                  <div className="flex min-w-max gap-2">
                    {TABS.map((tab) => (
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

                {activeTab === "summary" && (
                  <section className="space-y-5">
                    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                      <h2 className="text-lg font-semibold">Summary</h2>
                      <p className="mt-3 leading-7">
                        {implementationResult.implementation_summary}
                      </p>
                    </div>

                    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                      <h2 className="text-lg font-semibold">Source Sections</h2>
                      {implementationResult.source_sections.length === 0 ? (
                        <p className="mt-3 text-sm text-[var(--muted)]">
                          No source sections were returned.
                        </p>
                      ) : (
                        <div className="mt-4 grid gap-3 lg:grid-cols-2">
                          {implementationResult.source_sections.map((section) => (
                            <article
                              key={section.id}
                              className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <h3 className="font-semibold">{section.title}</h3>
                                <span className="text-xs text-[var(--muted)]">
                                  #{section.section_order}
                                </span>
                              </div>
                              <p className="mt-2 text-sm leading-6 text-[var(--muted)] line-clamp-5">
                                {section.content_preview}
                              </p>
                            </article>
                          ))}
                        </div>
                      )}
                    </div>
                  </section>
                )}

                {activeTab === "algorithm" && (
                  <section className="space-y-4">
                    {implementationResult.algorithm_steps.length === 0 ? (
                      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 text-sm text-[var(--muted)]">
                        No grounded algorithm steps were returned.
                      </div>
                    ) : (
                      implementationResult.algorithm_steps.map((step) => (
                        <article
                          key={`${step.order}-${step.title}`}
                          className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
                        >
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <span className="text-xs font-semibold uppercase tracking-wide text-[var(--primary)]">
                                Step {step.order}
                              </span>
                              <h2 className="mt-1 text-xl font-semibold">
                                {step.title}
                              </h2>
                            </div>
                          </div>
                          <p className="mt-3 leading-7">{step.description}</p>
                          <div className="mt-4 grid gap-4 md:grid-cols-3">
                            <ListBlock title="Inputs" items={step.inputs} />
                            <ListBlock title="Outputs" items={step.outputs} />
                            <ListBlock title="Evidence" items={step.evidence} />
                          </div>
                        </article>
                      ))
                    )}
                  </section>
                )}

                {activeTab === "gaps" && (
                  <section className="grid gap-4 lg:grid-cols-2">
                    {implementationResult.assumptions_and_gaps.length === 0 ? (
                      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 text-sm text-[var(--muted)]">
                        No assumptions or gaps were returned.
                      </div>
                    ) : (
                      implementationResult.assumptions_and_gaps.map((gap, index) => (
                        <article
                          key={`${gap.category}-${index}`}
                          className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-[var(--primary)]/10 px-2.5 py-1 text-xs font-medium text-[var(--primary)]">
                              {gap.category.replaceAll("_", " ")}
                            </span>
                            <span
                              className={`rounded-full border px-2.5 py-1 text-xs font-medium ${SEVERITY_STYLES[gap.severity]}`}
                            >
                              {gap.severity} severity
                            </span>
                          </div>
                          <p className="mt-4 leading-7">{gap.description}</p>
                          <ListBlock title="Evidence" items={gap.evidence} />
                        </article>
                      ))
                    )}
                  </section>
                )}

                {activeTab === "pseudocode" && (
                  <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                    <h2 className="text-lg font-semibold">Pseudocode</h2>
                    <pre className="mt-4 overflow-x-auto rounded-lg bg-[var(--background)] p-4 text-sm leading-6">
                      <code>{implementationResult.pseudocode}</code>
                    </pre>
                  </section>
                )}

                {activeTab === "code" && (
                  <section className="space-y-5">
                    {generatedCodeFiles.length === 0 ? (
                      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 text-sm text-[var(--muted)]">
                        No starter code files were returned.
                      </div>
                    ) : (
                      generatedCodeFiles.map((file) => (
                        <article
                          key={file.path}
                          className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]"
                        >
                          <div className="flex flex-col gap-3 border-b border-[var(--border)] px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                              <h2 className="font-semibold">{file.path}</h2>
                              <p className="mt-1 text-sm text-[var(--muted)]">
                                {file.purpose}
                              </p>
                            </div>
                            <div className="flex shrink-0 items-center gap-3">
                              {copyStatus[file.path] && (
                                <span className="text-xs text-[var(--muted)]">
                                  {copyStatus[file.path]}
                                </span>
                              )}
                              <button
                                onClick={() => handleCopyFile(file)}
                                className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-medium transition-colors hover:border-[var(--primary)]/30 hover:text-[var(--primary)]"
                              >
                                Copy
                              </button>
                            </div>
                          </div>
                          <pre className="overflow-x-auto bg-[var(--background)] p-5 text-sm leading-6">
                            <code>{file.content}</code>
                          </pre>
                        </article>
                      ))
                    )}
                  </section>
                )}

                {activeTab === "test" && (
                  <section className="grid gap-5 lg:grid-cols-2">
                    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                      <h2 className="text-lg font-semibold">Setup Notes</h2>
                      <ListBlock items={implementationResult.setup_notes} />
                    </div>
                    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                      <h2 className="text-lg font-semibold">Test Plan</h2>
                      <ListBlock items={implementationResult.test_plan} />
                    </div>
                  </section>
                )}
              </>
            )}
          </section>
        </div>
      </main>
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
