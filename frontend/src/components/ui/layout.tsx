import { ElementType, ReactNode } from "react";
import Link from "next/link";

import { cx } from "@/lib/cx";

/* ------------------------------------------------------------------
   The container rule: a box means a discrete module or an alert.
   Peer items in a list are never boxed. They get space and a hairline.
   If everything is a card, nothing is a module.
   ------------------------------------------------------------------ */

export function PageHeader({
  title,
  sub,
  end,
}: {
  title: ReactNode;
  sub?: ReactNode;
  /** Actions sit beside the thing they act on. */
  end?: ReactNode;
}) {
  if (!end) {
    return (
      <div>
        <h1 className="page-title">{title}</h1>
        {sub ? <p className="page-sub">{sub}</p> : null}
      </div>
    );
  }
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "var(--space-4xl)",
      }}
    >
      <div>
        <h1 className="page-title">{title}</h1>
        {sub ? <p className="page-sub">{sub}</p> : null}
      </div>
      <div style={{ display: "flex", gap: "var(--space-md)", flex: "none" }}>
        {end}
      </div>
    </div>
  );
}

export function Section({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={cx("section", className)}>{children}</section>;
}

export function SectionHead({
  children,
  end,
  level = 2,
}: {
  children: ReactNode;
  end?: ReactNode;
  /** 3 for a subgroup inside a section. Both render at the same size. */
  level?: 2 | 3;
}) {
  const Tag = level === 3 ? "h3" : "h2";
  return (
    <div className="section-head">
      <Tag>{children}</Tag>
      {end}
    </div>
  );
}

export function Split({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("split", className)}>{children}</div>;
}

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="toolbar">{children}</div>;
}

export function Panel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("panel", className)}>{children}</div>;
}

/** Uppercase is chrome, never content. This is one of the two places it appears. */
export function PanelHead({
  children,
  end,
}: {
  children: ReactNode;
  end?: ReactNode;
}) {
  return (
    <div className="panel-head">
      <span>{children}</span>
      {end ? <span className="normal">{end}</span> : null}
    </div>
  );
}

/** Prose inside a panel, as opposed to the rows a panel usually holds. */
export function PanelBody({ children }: { children: ReactNode }) {
  return <div className="panel-body">{children}</div>;
}

export function Row({
  children,
  end,
  as,
  href,
  onClick,
  className,
}: {
  children: ReactNode;
  end?: ReactNode;
  as?: ElementType;
  /** Makes the whole row a link. Takes precedence over onClick. */
  href?: string;
  onClick?: () => void;
  className?: string;
}) {
  const body = (
    <>
      <span>{children}</span>
      {end ? <span className="row-end">{end}</span> : null}
    </>
  );

  if (href) {
    return (
      <Link href={href} className={cx("row", className)}>
        {body}
      </Link>
    );
  }

  const Tag = as ?? (onClick ? "button" : "div");
  return (
    <Tag
      className={cx("row", className)}
      onClick={onClick}
      {...(Tag === "button" ? { type: "button" as const } : {})}
    >
      {body}
    </Tag>
  );
}

export function WarnPanel({
  title,
  children,
  actions,
}: {
  title: ReactNode;
  children: ReactNode;
  /** An alert that names a fix should be able to carry it. */
  actions?: ReactNode;
}) {
  return (
    <div className="warnpanel">
      <b>{title}</b>
      <p>{children}</p>
      {actions ? <div className="acts">{actions}</div> : null}
    </div>
  );
}

export function SelectionBar({
  count,
  children,
}: {
  count: number;
  children: ReactNode;
}) {
  return (
    <div className="selbar">
      <span className="n">{count} selected</span>
      <span className="selbar-end">{children}</span>
    </div>
  );
}

export function CodeBlock({
  path,
  purpose,
  content,
  onToggle,
  end,
}: {
  path: string;
  purpose?: ReactNode;
  /** Omit to render the header only, as a collapsed file. */
  content?: string;
  onToggle?: () => void;
  /** Controls for this file. A header carrying these is never itself a button. */
  end?: ReactNode;
}) {
  const HeadTag = onToggle && !end ? "button" : "div";
  return (
    <div className={cx("code", !content && "folded")}>
      <HeadTag
        className="code-head"
        onClick={onToggle && !end ? onToggle : undefined}
        {...(HeadTag === "button" ? { type: "button" as const } : {})}
      >
        <span className="path">{path}</span>
        {purpose || end ? (
          <span className="end">
            {purpose ? <span className="purpose">{purpose}</span> : null}
            {end}
          </span>
        ) : null}
      </HeadTag>
      {content ? <pre>{content}</pre> : null}
    </div>
  );
}

/* ---- Peer list items. Unboxed by rule. ---- */

export function Item({
  index,
  checkbox,
  children,
  onClick,
  className,
}: {
  /** A rank or ordinal. Mutually exclusive with checkbox. */
  index?: ReactNode;
  checkbox?: ReactNode;
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  const lead = checkbox ?? (index !== undefined ? <div className="rank">{index}</div> : null);
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      className={cx(
        "item",
        checkbox ? "checkable" : lead ? undefined : "flush",
        className,
      )}
      onClick={onClick}
      {...(Tag === "button" ? { type: "button" as const } : {})}
    >
      {lead}
      <div>{children}</div>
    </Tag>
  );
}

export function Step({
  n,
  title,
  children,
}: {
  n: ReactNode;
  title: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="step">
      <div className="n">{n}</div>
      <div>
        <h3>{title}</h3>
        {children}
      </div>
    </div>
  );
}

export function GapItem({
  category,
  severity,
  children,
}: {
  category: ReactNode;
  /** A Tag, graded high / med / quiet. Never a status pill. */
  severity: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="gap-item">
      <div className="top">
        <b>{category}</b>
        {severity}
      </div>
      {children}
    </div>
  );
}

export function PlainList({ items }: { items: ReactNode[] }) {
  return (
    <ul className="plainlist">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}
