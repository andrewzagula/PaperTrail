"use client";

import { ReactNode, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Books,
  Columns,
  IconContext,
  Lightbulb,
  MagnifyingGlass,
  SlidersHorizontal,
} from "@phosphor-icons/react";

import { cx } from "@/lib/cx";
import { Kbd } from "@/components/ui/display";
import { CommandPalette } from "./CommandPalette";

/* ------------------------------------------------------------------
   The shell is a wrapping flex row, never a grid: container queries
   cannot restyle the element that IS the container, so the topology
   lives on children the query can reach. See components.css.

   Five nav items. Workspace and Library were two entries pointing at
   one page; saved work now lives in the section that produced it.
   ------------------------------------------------------------------ */

interface NavEntry {
  href: string;
  label: string;
  icon: ReactNode;
  /** Path prefixes that should light this entry up. */
  owns: string[];
}

const NAV: NavEntry[] = [
  { href: "/", label: "Discover", icon: <MagnifyingGlass />, owns: ["/discover"] },
  { href: "/library", label: "Library", icon: <Books />, owns: ["/papers"] },
  { href: "/compare", label: "Compare", icon: <Columns />, owns: [] },
  { href: "/ideas", label: "Ideas", icon: <Lightbulb />, owns: [] },
  { href: "/settings", label: "Settings", icon: <SlidersHorizontal />, owns: [] },
];

function isActive(entry: NavEntry, pathname: string): boolean {
  if (entry.href === "/") {
    return pathname === "/" || entry.owns.some((p) => pathname.startsWith(p));
  }
  return (
    pathname === entry.href ||
    pathname.startsWith(`${entry.href}/`) ||
    entry.owns.some((p) => pathname.startsWith(p))
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const [paletteOpen, setPaletteOpen] = useState(false);

  /* Registered once, on the document, because the shortcut has to work
     wherever focus happens to be. The browser's own find-in-page is not
     bound to this combination, so nothing is being taken away. */
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  /* Stable, so the palette does not rebind its own listeners every render. */
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  return (
    <IconContext.Provider value={{ size: 15, weight: "regular" }}>
      <div className="app">
        <nav className="rail" aria-label="Main">
          {/* Search sits under the top of the rail, not pinned to the floor:
              it is a primary way in, and showing the shortcut beside it
              teaches the shortcut rather than only rewarding people who
              already know it. */}
          <button
            type="button"
            className="searchtrigger"
            onClick={() => setPaletteOpen(true)}
            aria-label="Search and commands"
          >
            <MagnifyingGlass aria-hidden />
            <span className="lbl">Search</span>
            <Kbd>&#8984;K</Kbd>
          </button>

          {NAV.map((entry) => {
            const active = isActive(entry, pathname);
            return (
              <Link
                key={entry.href}
                href={entry.href}
                className={cx("nav", active && "on")}
                aria-current={active ? "page" : undefined}
              >
                <span aria-hidden style={{ display: "flex" }}>
                  {entry.icon}
                </span>
                <span className="lbl">{entry.label}</span>
              </Link>
            );
          })}

          <div className="rail-spacer" />
        </nav>

        <div className="main">{children}</div>
      </div>

      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </IconContext.Provider>
  );
}

export function TopBar({
  crumb,
  end,
}: {
  crumb: ReactNode;
  end?: ReactNode;
}) {
  return (
    <div className="topbar">
      <span className="crumb">{crumb}</span>
      {end ? <span className="topbar-end">{end}</span> : null}
    </div>
  );
}

export function Body({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("body", className)}>{children}</div>;
}
