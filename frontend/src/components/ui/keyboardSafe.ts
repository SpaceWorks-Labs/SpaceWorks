import type { FocusEvent } from "react";

const TEXT_ENTRY = "input:not([type=checkbox]):not([type=radio]):not([type=range]):not([type=button]):not([type=submit]), textarea, select, [contenteditable='true']";

/**
 * Keeps a focused field visible once the on-screen keyboard has opened. The keyboard resizes the
 * visual viewport after focus lands, so the reveal waits for that resize instead of guessing.
 * Attach as `onFocus` on a dialog or drawer body (React focus events bubble like focusin).
 */
export function revealFieldAboveKeyboard(event: FocusEvent<HTMLElement>) {
  const field = event.target;
  const viewport = typeof window === "undefined" ? undefined : window.visualViewport;
  if (!viewport || !(field instanceof HTMLElement) || !field.matches(TEXT_ENTRY)) return;
  const reveal = () => field.scrollIntoView?.({ block: "nearest" });
  viewport.addEventListener("resize", reveal, { once: true });
  window.setTimeout(() => viewport.removeEventListener("resize", reveal), 1000);
}
