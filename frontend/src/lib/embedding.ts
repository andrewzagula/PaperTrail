/* ------------------------------------------------------------------
   Embedding state, in the words a person would use.

   The four statuses come from backend/app/services/paper_embeddings.py
   and are tracked per (paper, provider, model). Switching the embedding
   model in Settings therefore does not destroy anything: it makes the
   old vectors stale, and re-embedding is what closes the gap. That is
   the whole reason this file exists in one place rather than being
   re-explained on every screen that shows a status.
   ------------------------------------------------------------------ */

export const EMBEDDING_READY = "ready";

export const EMBEDDING_MEANING: Record<string, string> = {
  ready: "Embedded with the model currently set. Chat and comparison read it in full.",
  stale:
    "Embedded with a different model. Nothing was lost, but it is out of step with everything embedded since.",
  missing: "Never embedded. Chat and comparison cannot read this one yet.",
  failed: "The last attempt to embed it did not finish.",
};

/** True when re-embedding would change something. */
export function needsEmbedding(status: string): boolean {
  return status !== EMBEDDING_READY;
}

export function explainEmbedding(status: string): string {
  return EMBEDDING_MEANING[status] ?? `Embedding status: ${status}.`;
}

/** "3 papers" / "1 paper". Said often enough here to be worth naming. */
export function papersWord(count: number): string {
  return `${count} paper${count === 1 ? "" : "s"}`;
}
