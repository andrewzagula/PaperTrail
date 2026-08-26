import { ReactNode } from "react";

import { cx } from "@/lib/cx";

/* ------------------------------------------------------------------
   Three forms, three jobs. A reader can tell what kind of fact they
   are looking at before reading the words.

     StatusPill  filled pill   lifecycle state, colour carries valence
     Score/Num   plain mono    a measurement. Numbers are not states
     Tag         outline chip  a category or judgement, never a status
   ------------------------------------------------------------------ */

/** The lifecycle states the backend actually reports. */
export type StatusTone = "ok" | "run" | "bad" | "idle";

const BACKEND_STATUS: Record<string, StatusTone> = {
  complete: "ok",
  completed: "ok",
  ready: "ok",
  embedded: "ok",
  running: "run",
  pending: "run",
  stale: "run",
  partial: "run",
  failed: "bad",
  error: "bad",
  missing: "idle",
  idle: "idle",
  not_started: "idle",
};

/** Maps a backend status string to a tone, defaulting to idle. */
export function toneFor(status: string): StatusTone {
  return BACKEND_STATUS[status.toLowerCase()] ?? "idle";
}

export function StatusPill({
  tone,
  children,
  className,
}: {
  tone: StatusTone;
  children: ReactNode;
  className?: string;
}) {
  return <span className={cx("st", tone, className)}>{children}</span>;
}

/** A measurement the interface is reporting. Never a state. */
export function Score({
  weak,
  children,
  className,
}: {
  weak?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return <span className={cx("score", weak && "weak", className)}>{children}</span>;
}

/** Counts, timings, dates, ids. Muted by default. */
export function Num({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <span className={cx("num", className)}>{children}</span>;
}

export type TagTone = "default" | "quiet" | "high" | "med";

/** A category or a judgement. Severity grades use this so they never
    read as a pipeline status. */
export function Tag({
  tone = "default",
  children,
  className,
}: {
  tone?: TagTone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={cx("tag", tone !== "default" && tone, className)}>
      {children}
    </span>
  );
}

/** Where a claim came from in the source paper. */
export function Cite({ children }: { children: ReactNode }) {
  return <span className="cite">{children}</span>;
}

export function Kbd({ children }: { children: ReactNode }) {
  return <span className="kbd">{children}</span>;
}

/** Generated output names itself as generated, at the point it appears. */
export function Provenance({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <p className={cx("prov", className)}>{children}</p>;
}

export function Spinner({ label = "Working" }: { label?: string }) {
  return <span className="spinner" role="status" aria-label={label} />;
}

export function Working({ children = "Working" }: { children?: ReactNode }) {
  return (
    <span className="working">
      <Spinner />
      {children}
    </span>
  );
}

export type StageState = "done" | "now" | "todo";

/* Long, failable work is the normal case here, so the interface names
   the steps rather than showing one spinner and hoping. */
export function Stage({
  state,
  children,
  end,
}: {
  state: StageState;
  children: ReactNode;
  end?: ReactNode;
}) {
  return (
    <div className={cx("stage", state)}>
      <span className="dot" aria-hidden />
      <span className="t">{children}</span>
      {end}
    </div>
  );
}
