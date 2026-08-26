export type ClassValue = string | false | null | undefined;

/** Joins class names, dropping falsey entries. */
export function cx(...parts: ClassValue[]): string {
  return parts.filter(Boolean).join(" ");
}
