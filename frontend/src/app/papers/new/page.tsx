"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { UploadSimple } from "@phosphor-icons/react";

import {
  Body,
  Button,
  Dropzone,
  Field,
  Input,
  Notice,
  Provenance,
  Section,
  TopBar,
  Working,
} from "@/components";
import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type PendingAction = "arxiv" | "pdf";

/* Accepts a full link, a bare id, or an id with a version suffix, because
   all three are things a person actually has on their clipboard. */
const ARXIV_PATTERN = /(arxiv\.org\/(abs|pdf)\/)?\d{4}\.\d{4,5}(v\d+)?/i;

export default function NewPaper() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [arxivUrl, setArxivUrl] = useState("");
  const [arxivError, setArxivError] = useState("");
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [droppedName, setDroppedName] = useState("");

  const loading = pendingAction !== null;
  const loadingMessage =
    pendingAction === "arxiv"
      ? "Fetching the metadata, downloading the PDF, splitting it into sections, and embedding it."
      : "Reading the PDF, extracting the text, splitting it into sections, and embedding it.";

  async function handleArxivSubmit(event: React.FormEvent) {
    event.preventDefault();
    const value = arxivUrl.trim();
    if (!value || loading) return;

    if (!ARXIV_PATTERN.test(value)) {
      setArxivError(
        "That is not an arXiv address. Paste a link like arxiv.org/abs/1706.03762, or just the id on its own.",
      );
      return;
    }

    setArxivError("");
    setPendingAction("arxiv");
    setError("");

    try {
      const res = await fetch(`${API_URL}/papers/ingest/arxiv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arxiv_url: value }),
      });

      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Failed to add this paper"));
      }

      const data = await res.json();
      router.push(`/papers/${data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setPendingAction(null);
    }
  }

  async function handleFileUpload(file: File) {
    if (loading) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError(`${file.name} is not a PDF. Only PDF files can be read.`);
      return;
    }

    setPendingAction("pdf");
    setError("");
    setDroppedName(file.name);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_URL}/papers/ingest/pdf`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Failed to add this paper"));
      }

      const data = await res.json();
      router.push(`/papers/${data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setPendingAction(null);
    }
  }

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }

  return (
    <>
      <TopBar
        crumb={
          <>
            <Link href="/library" className="lnk">
              Library
            </Link>{" "}
            <span aria-hidden>/</span> <b>Add paper</b>
          </>
        }
      />
      <Body>
        <h1 className="page-title">Add a paper</h1>
        <p className="page-sub">
          Two ways in. Either one ends with the paper fetched, split into
          sections, and embedded for chat.
        </p>

        <Section>
          <form onSubmit={handleArxivSubmit}>
            <Field label="arXiv link or id" error={arxivError || undefined}>
              <div className="line">
                <Input
                  value={arxivUrl}
                  onChange={(event) => {
                    setArxivUrl(event.target.value);
                    setArxivError("");
                  }}
                  placeholder="https://arxiv.org/abs/1706.03762"
                  disabled={loading}
                  invalid={Boolean(arxivError)}
                />
                <Button type="submit" disabled={loading || !arxivUrl.trim()}>
                  {pendingAction === "arxiv" ? "Fetching" : "Fetch"}
                </Button>
              </div>
            </Field>
          </form>

          <div className="orline">or</div>

          <div
            onDragOver={(event) => {
              event.preventDefault();
              if (!loading) setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <Dropzone
              armed={dragOver}
              disabled={loading}
              onClick={() => fileInputRef.current?.click()}
              icon={<UploadSimple aria-hidden />}
              title={dragOver ? "Release to add" : "Drop a PDF here"}
              hint={dragOver ? "PDF only" : "or choose a file"}
            />
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            hidden
            disabled={loading}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) handleFileUpload(file);
              event.target.value = "";
            }}
          />
        </Section>

        {error ? (
          <Section>
            <Notice tone="bad">{error}</Notice>
          </Section>
        ) : null}

        {loading ? (
          <Section className="col-narrow">
            <Working>{loadingMessage}</Working>
            {droppedName && pendingAction === "pdf" ? (
              <Provenance>{droppedName}</Provenance>
            ) : null}
            <Provenance>
              This runs in one go, so stay on this page until it finishes.
            </Provenance>
          </Section>
        ) : null}
      </Body>
    </>
  );
}
