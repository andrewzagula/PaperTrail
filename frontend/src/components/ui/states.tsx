import { ReactNode } from "react";
import Link from "next/link";

import { cx } from "@/lib/cx";

/* ------------------------------------------------------------------
   Loading, absence, and failure are states this product spends real
   time in: every page here waits on a model or a fetch. They get
   designed treatment rather than a spinner and a stack trace.
   ------------------------------------------------------------------ */

/** Nothing to show inside a section that otherwise would have content. */
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

/** A whole page that cannot show what it was asked for. */
export function Blank({
  kind,
  quiet,
  title,
  children,
  actions,
}: {
  /** What kind of stop this is, in two or three words. */
  kind: ReactNode;
  /** True when nothing is wrong and there is simply nothing here yet. */
  quiet?: boolean;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="blank">
      <p className={cx("kind", quiet && "quiet")}>{kind}</p>
      <h2>{title}</h2>
      {children ? <p>{children}</p> : null}
      {actions ? <div className="acts">{actions}</div> : null}
    </div>
  );
}

export function Skeleton({
  w,
  h,
  className,
}: {
  w?: string;
  h?: number;
  className?: string;
}) {
  return (
    <div
      className={cx("skel", className)}
      style={{ width: w, height: h }}
      aria-hidden
    />
  );
}

/** The shape a page holds while it loads: title, subtitle, a body block. */
export function PageSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="skel-stack" role="status" aria-label="Loading">
      <Skeleton w="220px" h={22} />
      <Skeleton w="min(560px, 100%)" h={14} />
      <div style={{ height: "var(--space-3xl)" }} />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} w={i % 3 === 2 ? "62%" : "100%"} />
      ))}
    </div>
  );
}

/** A pointer to another record. Tags describe, chips navigate. */
export function Chip({
  href,
  children,
  title,
}: {
  /** Omit for a chip with no record behind it. */
  href?: string;
  children: ReactNode;
  title?: string;
}) {
  if (!href) {
    return (
      <span className="chip plain" title={title}>
        {children}
      </span>
    );
  }
  return (
    <Link href={href} className="chip" title={title}>
      {children}
    </Link>
  );
}

export function ChipRow({ children }: { children: ReactNode }) {
  return <div className="chiprow">{children}</div>;
}

/** Label over value. Says so explicitly when a model returned nothing. */
export function Fact({
  k,
  children,
  none = "Not returned.",
}: {
  k: ReactNode;
  children?: ReactNode;
  none?: ReactNode;
}) {
  const empty =
    children === undefined ||
    children === null ||
    children === "" ||
    children === false;
  return (
    <div className="fact">
      <span className="k">{k}</span>
      <div className={cx("v", empty && "none")}>{empty ? none : children}</div>
    </div>
  );
}

export function Facts({ children }: { children: ReactNode }) {
  return <div className="facts">{children}</div>;
}

/** Destructive confirmation, shown where the action was requested. */
export function Confirm({
  title,
  children,
  error,
  actions,
}: {
  title: ReactNode;
  children?: ReactNode;
  error?: ReactNode;
  actions: ReactNode;
}) {
  return (
    <div className="confirm" role="alertdialog" aria-label={String(title)}>
      <b>{title}</b>
      {children ? <p>{children}</p> : null}
      {error ? (
        <p className="notice bad" role="alert" style={{ marginTop: "var(--space-md)" }}>
          {error}
        </p>
      ) : null}
      <div className="acts">{actions}</div>
    </div>
  );
}

export function Notice({
  tone = "ok",
  children,
}: {
  tone?: "ok" | "bad" | "quiet";
  children: ReactNode;
}) {
  return (
    <p
      className={cx("notice", tone !== "ok" && tone)}
      role={tone === "bad" ? "alert" : "status"}
    >
      {children}
    </p>
  );
}
