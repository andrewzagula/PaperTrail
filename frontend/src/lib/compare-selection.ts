const STORAGE_KEY = "papertrail.compare-selection";

export const MAX_COMPARE_SELECTION = 5;

function normalizeSelection(ids: string[]): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];

  for (const rawId of ids) {
    const id = rawId.trim();
    if (!id || seen.has(id)) {
      continue;
    }

    seen.add(id);
    normalized.push(id);

    if (normalized.length === MAX_COMPARE_SELECTION) {
      break;
    }
  }

  return normalized;
}

export function getStoredCompareSelection(): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const rawValue = window.localStorage.getItem(STORAGE_KEY);
    if (!rawValue) {
      return [];
    }

    const parsed = JSON.parse(rawValue);
    if (!Array.isArray(parsed)) {
      return [];
    }

    return normalizeSelection(parsed.filter((value): value is string => typeof value === "string"));
  } catch {
    return [];
  }
}

export function setStoredCompareSelection(ids: string[]): string[] {
  const normalized = normalizeSelection(ids);

  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    } catch {}
  }

  return normalized;
}

export function mergeCompareSelection(
  preferredIds: string[],
  fallbackIds: string[],
): string[] {
  return normalizeSelection([...preferredIds, ...fallbackIds]);
}

export function addPaperToCompare(paperId: string): {
  ids: string[];
  added: boolean;
  reason?: "duplicate" | "limit";
} {
  const current = getStoredCompareSelection();

  if (current.includes(paperId)) {
    return { ids: current, added: false, reason: "duplicate" };
  }

  if (current.length >= MAX_COMPARE_SELECTION) {
    return { ids: current, added: false, reason: "limit" };
  }

  const next = setStoredCompareSelection([...current, paperId]);
  return { ids: next, added: true };
}
