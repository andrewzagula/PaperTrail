"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import {
  Blank,
  Body,
  Button,
  Cite,
  CodeBlock,
  Empty,
  Input,
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
  Segmented,
  Step,
  StatusPill,
  Tag,
  Toolbar,
  TopBar,
  WarnPanel,
  Working,
} from "@/components";
import type { TagTone } from "@/components";
import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type TargetFramework = "pytorch" | "generic-python";
type GapSeverity = "low" | "medium" | "high";

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

const FRAMEWORK_OPTIONS: { value: TargetFramework; label: string }[] = [
  { value: "pytorch", label: "PyTorch" },
  { value: "generic-python", label: "Plain Python" },
];

const SEVERITY_TONES: Record<GapSeverity, TagTone> = {
  high: "high",
  medium: "med",
  low: "quiet",
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
          throw new Error(await getApiErrorMessage(res, "Paper not found."));
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

  const generationDisabled = generationLoading || paperLoading || Boolean(paperError);

  const clearResultState = () => {
    setImplementationResult(null);
    setGenerationError("");
    setSaveTitle("");
    setSaveLoading(false);
    setSaveError("");
    setSaveSuccess("");
    setLastSavedKey("");
    setCopyStatus({});
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
    if (generationLoading) {
      return;
    }

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
        throw new Error(
          await getApiErrorMessage(res, "Implementation generation failed."),
        );
      }

      const data: ImplementationResponse = await res.json();
      setImplementationResult(data);
      setSaveTitle(createDefaultImplementationTitle(data));
      setLastSavedKey("");
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
      setSaveError("Give this plan a title before saving.");
      setSaveSuccess("");
      return;
    }

    const saveKey = createSaveKey(implementationResult, normalizedTitle);
    if (saveKey === lastSavedKey) {
      setSaveError("This plan is already saved under that title.");
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
        throw new Error(
          await getApiErrorMessage(res, "Failed to save implementation."),
        );
      }

      const data: SaveImplementationResponse = await res.json();
      setSaveTitle(data.title);
      setSaveSuccess(`Saved to your library as "${data.title}".`);
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
      <>
        <TopBar crumb={<b>Implement</b>} />
        <Body>
          <PageSkeleton />
        </Body>
      </>
    );
  }

  if (paperError || !paper) {
    return (
      <>
        <TopBar crumb={<b>Implement</b>} />
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
            {paperError || "Paper not found."}
          </Blank>
        </Body>
      </>
    );
  }

  const result = implementationResult;

  return (
    <>
      <TopBar
        crumb={
          <>
            <Link href="/library" className="lnk">
              Library
            </Link>{" "}
            <span aria-hidden>/</span>{" "}
            <Link href={`/papers/${paper.id}`} className="lnk">
              {paper.title}
            </Link>{" "}
            <span aria-hidden>/</span> <b>Implement</b>
          </>
        }
        end={
          result ? (
            <>
              <StatusPill tone="ok">generated</StatusPill>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSaveImplementation}
                disabled={saveLoading}
              >
                {saveLoading ? "Saving" : "Save plan"}
              </Button>
            </>
          ) : undefined
        }
      />
      <Body>
        <PageHeader
          title="Implementation plan"
          sub={
            <>
              From {paper.title}
              {paper.authors ? <Num> {paper.authors}</Num> : null}
            </>
          }
          end={
            result ? (
              <Button
                variant="ghost"
                onClick={handleGenerateImplementation}
                disabled={generationDisabled}
              >
                {generationLoading ? "Working" : "Regenerate"}
              </Button>
            ) : undefined
          }
        />

        <Section>
          <Toolbar>
            <Segmented
              label="Target framework"
              value={targetFramework}
              onChange={handleFrameworkChange}
              options={FRAMEWORK_OPTIONS}
            />
            <Input
              value={focus}
              maxLength={1000}
              disabled={generationLoading}
              onChange={(event) => handleFocusChange(event.target.value)}
              placeholder="Focus, if you have one: training loop, inference only, the loss"
              aria-label="Focus"
            />
            {!result ? (
              <Button onClick={handleGenerateImplementation} disabled={generationDisabled}>
                {generationLoading ? "Generating" : "Generate plan"}
              </Button>
            ) : null}
          </Toolbar>
          <Provenance>
            Python. Written by the model from the paper&apos;s own text. It is a
            starting point for your implementation, not a reference one, and it has
            not been run.
          </Provenance>
          {generationError ? (
            <div style={{ marginTop: "var(--space-lg)" }}>
              <Notice tone="bad">{generationError}</Notice>
            </div>
          ) : null}
        </Section>

        {generationLoading ? (
          <Section>
            <Working>
              Reading the method, pulling out steps, drafting files, and carrying
              the caveats forward. This takes a few minutes.
            </Working>
          </Section>
        ) : null}

        {!result && !generationLoading ? (
          <Section>
            <Blank
              kind="Nothing generated yet"
              quiet
              title="No plan for this paper yet"
            >
              Generating produces a summary, ordered algorithm steps with their
              inputs and evidence, the assumptions the model had to make,
              pseudocode, starter files, and a test plan. Nothing runs until you
              ask for it.
            </Blank>
          </Section>
        ) : null}

        {result ? (
          <>
            {result.warnings.length > 0 ? (
              <Section>
                <WarnPanel
                  title={
                    result.warnings.length === 1
                      ? "One claim could not be traced"
                      : `${result.warnings.length} claims could not be traced`
                  }
                >
                  {result.warnings.join(" ")}
                </WarnPanel>
              </Section>
            ) : null}

            <Section>
              <SectionHead>Summary</SectionHead>
              <div className="reading">
                <p>{result.implementation_summary}</p>
              </div>
            </Section>

            <Section className="col-narrow">
              <SectionHead
                end={
                  <Num>
                    {result.algorithm_steps.length} step
                    {result.algorithm_steps.length === 1 ? "" : "s"}
                  </Num>
                }
              >
                Algorithm steps
              </SectionHead>
              {result.algorithm_steps.length === 0 ? (
                <Empty>No grounded algorithm steps were returned.</Empty>
              ) : (
                result.algorithm_steps.map((step, index) => (
                  <Step
                    key={`${step.order}-${index}`}
                    n={String(step.order).padStart(2, "0")}
                    title={step.title}
                  >
                    <p>{step.description}</p>
                    {step.inputs.length > 0 || step.outputs.length > 0 ? (
                      <div className="io">
                        <Io k="in" items={step.inputs} />
                        <Io k="out" items={step.outputs} />
                      </div>
                    ) : null}
                    {step.evidence.length > 0 ? (
                      <Cite>{step.evidence.join(" · ")}</Cite>
                    ) : null}
                  </Step>
                ))
              )}
            </Section>

            <Section className="col-narrow">
              <SectionHead
                end={<Num>{result.assumptions_and_gaps.length} found</Num>}
              >
                Assumptions and gaps
              </SectionHead>
              {result.assumptions_and_gaps.length === 0 ? (
                <Empty>The model reported no assumptions or gaps.</Empty>
              ) : (
                result.assumptions_and_gaps.map((gap, index) => (
                  <div key={`${gap.category}-${index}`} className="gap-item">
                    <div className="top">
                      <b>{gap.category.replaceAll("_", " ")}</b>
                      <Tag tone={SEVERITY_TONES[gap.severity]}>{gap.severity}</Tag>
                    </div>
                    <p>{gap.description}</p>
                    {gap.evidence.length > 0 ? (
                      <Cite>{gap.evidence.join(" · ")}</Cite>
                    ) : null}
                  </div>
                ))
              )}
            </Section>

            <Section className="col-narrow">
              <SectionHead>Pseudocode</SectionHead>
              {result.pseudocode ? (
                <CodeBlock path="pseudocode" content={result.pseudocode} />
              ) : (
                <Empty>No pseudocode was returned.</Empty>
              )}
            </Section>

            <Section className="col-narrow">
              <SectionHead
                end={
                  <Num>
                    {result.starter_code.length} file
                    {result.starter_code.length === 1 ? "" : "s"}
                  </Num>
                }
              >
                Starter code
              </SectionHead>
              {result.starter_code.length === 0 ? (
                <Empty>No starter files were returned.</Empty>
              ) : (
                result.starter_code.map((file) => (
                  <CodeBlock
                    key={file.path}
                    path={file.path}
                    purpose={file.purpose}
                    content={file.content}
                    end={
                      <>
                        {copyStatus[file.path] ? (
                          <Notice
                            tone={
                              copyStatus[file.path] === "Copied" ? "quiet" : "bad"
                            }
                          >
                            {copyStatus[file.path]}
                          </Notice>
                        ) : null}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCopyFile(file)}
                        >
                          Copy
                        </Button>
                      </>
                    }
                  />
                ))
              )}
            </Section>

            <Section className="col-narrow">
              <SectionHead>Before you run it</SectionHead>
              {result.setup_notes.length === 0 ? (
                <Empty>No setup notes were returned.</Empty>
              ) : (
                <PlainList items={result.setup_notes} />
              )}
            </Section>

            <Section className="col-narrow">
              <SectionHead>How to check it works</SectionHead>
              {result.test_plan.length === 0 ? (
                <Empty>No test plan was returned.</Empty>
              ) : (
                <PlainList items={result.test_plan} />
              )}
            </Section>

            {result.source_sections.length > 0 ? (
              <Section className="col-narrow">
                <SectionHead end={<Num>{result.source_sections.length}</Num>}>
                  Sections this was built from
                </SectionHead>
                <Panel>
                  <PanelBody>
                    {result.source_sections.map((section) => (
                      <p key={section.id}>
                        <b>{section.title}</b> {section.content_preview}
                      </p>
                    ))}
                  </PanelBody>
                </Panel>
              </Section>
            ) : null}

            <Section className="col-narrow">
              <SectionHead>Save this plan</SectionHead>
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
                  placeholder="Title for this plan"
                  invalid={Boolean(saveError)}
                  style={{ flex: "1 1 320px" }}
                />
                <Button onClick={handleSaveImplementation} disabled={saveLoading}>
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
