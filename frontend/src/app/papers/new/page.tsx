"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function NewPaper() {
  const router = useRouter();
  const [arxivUrl, setArxivUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  async function handleArxivSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!arxivUrl.trim()) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/papers/ingest/arxiv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arxiv_url: arxivUrl }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to ingest paper");
      }

      const data = await res.json();
      router.push(`/papers/${data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function handleFileUpload(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a PDF file");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_URL}/papers/ingest/pdf`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to ingest paper");
      }

      const data = await res.json();
      router.push(`/papers/${data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }

  return (
    <div className="min-h-screen p-8 max-w-2xl mx-auto">
      <a
        href="/"
        className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
      >
        &larr; Back
      </a>

      <h1 className="text-3xl font-bold mt-6 mb-2">Add a Paper</h1>
      <p className="text-[var(--muted)] mb-8">
        Paste an arXiv link or upload a PDF to get started.
      </p>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}
      <form onSubmit={handleArxivSubmit} className="mb-8">
        <label className="block text-sm font-medium mb-2">arXiv URL</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={arxivUrl}
            onChange={(e) => setArxivUrl(e.target.value)}
            placeholder="https://arxiv.org/abs/2301.00001"
            disabled={loading}
            className="flex-1 px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--foreground)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)] disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !arxivUrl.trim()}
            className="px-6 py-3 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Processing..." : "Ingest"}
          </button>
        </div>
      </form>

      <div className="flex items-center gap-4 mb-8">
        <div className="flex-1 h-px bg-[var(--border)]" />
        <span className="text-sm text-[var(--muted)]">or</span>
        <div className="flex-1 h-px bg-[var(--border)]" />
      </div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
          dragOver
            ? "border-[var(--primary)] bg-[var(--primary)]/5"
            : "border-[var(--border)]"
        } ${loading ? "opacity-50 pointer-events-none" : ""}`}
      >
        <p className="text-[var(--muted)] mb-4">
          Drag and drop a PDF here, or click to browse
        </p>
        <label className="inline-block px-6 py-3 bg-[var(--card)] border border-[var(--border)] rounded-lg cursor-pointer hover:bg-[var(--border)] transition-colors">
          <span className="font-medium">Choose PDF</span>
          <input
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFileUpload(file);
            }}
            disabled={loading}
          />
        </label>
      </div>

      {loading && (
        <div className="mt-8 text-center">
          <div className="inline-block w-6 h-6 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[var(--muted)] mt-3">
            Extracting text, splitting sections, generating embeddings...
          </p>
        </div>
      )}
    </div>
  );
}
