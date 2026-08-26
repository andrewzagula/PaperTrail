"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { MagnifyingGlass } from "@phosphor-icons/react";

import { cx } from "@/lib/cx";
import { Kbd } from "@/components/ui/display";

/* ------------------------------------------------------------------
   The palette never animates. It is a hundred-times-a-day action, and
   an entrance on it makes the whole app feel slow. It also never runs
   anything that costs money or destroys data: every row here is a
   place to go, so Enter is always safe to press without reading.

   There is no search endpoint, and there does not need to be. This is
   one person's library on one machine, so the three list endpoints are
   fetched whole on open and filtered in the browser. That is faster
   than a round trip per keystroke would be.
   ------------------------------------------------------------------ */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** How many rows a group shows before the label starts saying "8 of 23". */
const GROUP_LIMIT = 8;

/** With no query typed the palette is a recent-things list, not a dump. */
const RESTING_LIMIT = 4;

interface PaletteEntry {
  id: string;
  group: string;
  label: string;
  /** Right-aligned, and searched along with the label. */
  meta?: string;
  href: string;
}

interface PaletteGroup {
  name: string;
  shown: PaletteEntry[];
  total: number;
}

const ACTIONS: PaletteEntry[] = [
  { id: "act-discover", group: "Actions", label: "Ask a research question", meta: "Discover", href: "/" },
  { id: "act-add", group: "Actions", label: "Add a paper", meta: "arXiv or PDF", href: "/papers/new" },
  { id: "act-library", group: "Actions", label: "Open your library", meta: "Library", href: "/library" },
  { id: "act-compare", group: "Actions", label: "Compare papers", meta: "Compare", href: "/compare" },
  { id: "act-ideas", group: "Actions", label: "Generate ideas", meta: "Ideas", href: "/ideas" },
  { id: "act-settings", group: "Actions", label: "Change providers and models", meta: "Settings", href: "/settings" },
];

interface FetchedPaper {
  id: string;
  title: string;
  authors: string | null;
  embedding_status: string;
}

interface FetchedSavedItem {
  id: string;
  title: string;
  item_type: string;
}

interface FetchedRun {
  id: string;
  question: string;
  status: string;
}

const SAVED_LABELS: Record<string, string> = {
  comparison: "Comparison",
  idea: "Ideas",
  implementation: "Plan",
};

async function loadEntries(): Promise<PaletteEntry[]> {
  const [papersRes, savedRes, runsRes] = await Promise.all([
    fetch(`${API_URL}/papers/`),
    fetch(`${API_URL}/workspace/saved-items`),
    fetch(`${API_URL}/discover/`),
  ]);

  if (!papersRes.ok || !savedRes.ok || !runsRes.ok) {
    throw new Error("Could not reach the local server.");
  }

  const papers: FetchedPaper[] = await papersRes.json();
  const saved: FetchedSavedItem[] = await savedRes.json();
  const runs: FetchedRun[] = await runsRes.json();

  return [
    ...papers.map((paper) => ({
      id: `paper-${paper.id}`,
      group: "Papers",
      label: paper.title,
      meta: paper.authors ?? undefined,
      href: `/papers/${paper.id}`,
    })),
    ...saved.map((item) => ({
      id: `saved-${item.id}`,
      group: "Saved work",
      label: item.title,
      meta: SAVED_LABELS[item.item_type] ?? item.item_type,
      href: `/library/saved/${item.id}`,
    })),
    ...runs.map((run) => ({
      id: `run-${run.id}`,
      group: "Discovery",
      label: run.question,
      meta: run.status,
      href: `/discover/${run.id}`,
    })),
  ];
}

const GROUP_ORDER = ["Actions", "Papers", "Saved work", "Discovery"];

function groupEntries(entries: PaletteEntry[], query: string): PaletteGroup[] {
  const needle = query.trim().toLowerCase();
  const limit = needle ? GROUP_LIMIT : RESTING_LIMIT;

  return GROUP_ORDER.map((name) => {
    const matching = entries.filter((entry) => {
      if (entry.group !== name) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${entry.label} ${entry.meta ?? ""}`.toLowerCase().includes(needle);
    });

    // Actions is a fixed list of six. Truncating it would hide a way in.
    const shown = name === "Actions" ? matching : matching.slice(0, limit);
    return { name, shown, total: matching.length };
  }).filter((group) => group.shown.length > 0);
}

export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  const [query, setQuery] = useState("");
  const [entries, setEntries] = useState<PaletteEntry[]>([]);
  const [loadError, setLoadError] = useState("");
  const [cursor, setCursor] = useState(0);

  /* Refetched on every open rather than cached: a paper added a minute ago
     missing from search would be a worse bug than three local requests. */
  useEffect(() => {
    if (!open) {
      return;
    }

    setQuery("");
    setCursor(0);
    setLoadError("");
    // Captured before the input takes focus, or the thing to go back to
    // would be the palette's own field.
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();

    let live = true;
    loadEntries()
      .then((loaded) => {
        if (live) {
          setEntries(loaded);
        }
      })
      .catch((err) => {
        if (live) {
          setEntries([]);
          setLoadError(
            err instanceof Error ? err.message : "Could not reach the local server.",
          );
        }
      });

    return () => {
      live = false;
    };
  }, [open]);

  /* The page behind an overlay should not scroll under it, and whoever was
     working before it opened should get their place back when it closes. */
  useEffect(() => {
    if (!open) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
      returnFocusRef.current?.focus?.();
    };
  }, [open]);

  /* Escape is bound to the document rather than the input, because a click
     on the box's own padding takes focus off the input and Escape has to
     keep working from wherever focus landed. */
  useEffect(() => {
    if (!open) {
      return;
    }
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [open, onClose]);

  const groups = useMemo(
    () => groupEntries([...ACTIONS, ...entries], query),
    [entries, query],
  );

  const flat = useMemo(() => groups.flatMap((group) => group.shown), [groups]);

  const active = flat[Math.min(cursor, flat.length - 1)];

  const go = useCallback(
    (entry: PaletteEntry | undefined) => {
      if (!entry) {
        return;
      }
      onClose();
      router.push(entry.href);
    },
    [onClose, router],
  );

  /* Keeping the highlighted row on screen is the whole point of arrow keys. */
  useEffect(() => {
    if (!active) {
      return;
    }
    const node = listRef.current?.querySelector(`[data-entry="${active.id}"]`);
    node?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) {
    return null;
  }

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setCursor((current) => (flat.length ? (current + 1) % flat.length : 0));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setCursor((current) =>
        flat.length ? (current - 1 + flat.length) % flat.length : 0,
      );
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      go(active);
    }
  };

  return (
    <div
      className="overlay"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className="overlay-box"
        role="dialog"
        aria-modal="true"
        aria-label="Search and commands"
      >
        <div className="pal-in">
          <MagnifyingGlass aria-hidden />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setCursor(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Search papers, saved work, and runs"
            aria-label="Search papers, saved work, and runs"
            role="combobox"
            aria-expanded
            aria-controls="pal-list"
            aria-activedescendant={active ? `pal-${active.id}` : undefined}
            autoComplete="off"
            spellCheck={false}
          />
        </div>

        <div className="pal-list" id="pal-list" role="listbox" ref={listRef}>
          {flat.length === 0 ? (
            <p className="pal-empty">
              {loadError
                ? `${loadError} Actions still work; the rest of your library is not loaded.`
                : `Nothing matches ${query.trim()}.`}
            </p>
          ) : (
            groups.map((group) => (
              <div key={group.name}>
                <div className="pal-label">
                  <span>{group.name}</span>
                  {group.shown.length < group.total ? (
                    <span className="n">
                      {group.shown.length} of {group.total}
                    </span>
                  ) : null}
                </div>
                {group.shown.map((entry) => (
                  <div
                    key={entry.id}
                    id={`pal-${entry.id}`}
                    data-entry={entry.id}
                    role="option"
                    aria-selected={entry.id === active?.id}
                    className={cx("pal-row", entry.id === active?.id && "on")}
                    onMouseMove={() => setCursor(flat.indexOf(entry))}
                    onClick={() => go(entry)}
                  >
                    <span className="t">{entry.label}</span>
                    {entry.meta ? <span className="k">{entry.meta}</span> : null}
                  </div>
                ))}
              </div>
            ))
          )}
        </div>

        <div className="pal-foot">
          <span>
            <Kbd>&#8593;</Kbd>
            <Kbd>&#8595;</Kbd> move
          </span>
          <span>
            <Kbd>&#8629;</Kbd> open
          </span>
          <span>
            <Kbd>esc</Kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}
