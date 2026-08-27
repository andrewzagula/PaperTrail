"use client";

import { createContext, useContext } from "react";

/* ------------------------------------------------------------------
   The paper itself is fetched once, by the layout, and shared with
   every panel under it. Both the panels page and the plan page used to
   fetch it separately, which is why moving between them flashed a
   loading state and rebuilt a header that had not changed.
   ------------------------------------------------------------------ */

export interface PaperSection {
  id: string;
  section_title: string;
  section_order: number;
  content: string;
}

export interface Breakdown {
  problem: string;
  method: string;
  key_contributions: string;
  results: string;
  limitations: string;
  future_work: string;
}

export interface Paper {
  id: string;
  title: string;
  authors: string | null;
  abstract: string | null;
  arxiv_url: string | null;
  created_at: string;
  structured_breakdown: Breakdown | null;
  sections: PaperSection[];
  embedding_status: string;
  embedding_provider: string;
  embedding_model: string;
  embedded_at: string | null;
}

/** The three panels that share one route. The plan is a route of its own. */
export type TabKey = "breakdown" | "chat" | "sections" | "paper";

export interface PaperContextValue {
  paper: Paper;
  /** For a panel that changes the paper: generating a breakdown, re-embedding. */
  setPaper: (paper: Paper) => void;
  tab: TabKey;
  /** Also used by a citation jumping the reader to Sections. */
  setTab: (tab: TabKey) => void;
}

const PaperContext = createContext<PaperContextValue | null>(null);

export const PaperProvider = PaperContext.Provider;

export function usePaper(): PaperContextValue {
  const value = useContext(PaperContext);
  if (!value) {
    throw new Error("usePaper must be called inside the paper layout.");
  }
  return value;
}
