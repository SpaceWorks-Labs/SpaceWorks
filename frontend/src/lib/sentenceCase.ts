/** Fallback label for an unknown server code: "pending_review" becomes "Pending review". */
export function sentenceCase(code: string): string {
  const words = code.replace(/[_-]+/g, " ").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
