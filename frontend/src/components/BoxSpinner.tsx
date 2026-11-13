import { useSyncExternalStore } from "react";
import { currentTheme, subscribeTheme } from "../lib/theme";
import { t } from "@lingui/core/macro";
import { BOX, boxGroundColour, ensureBoxCss } from "./boxOpen/shared";

/** The bare looping artwork (decorative, never focusable); `BoxSpinner` and the `Skeleton` placeholder wrap it. */
export function BoxArt({ size, mono = false }: { size: number; mono?: boolean }) {
  ensureBoxCss();
  // Re-read the host ground when its theme changes so the released mono artwork follows its host.
  useSyncExternalStore(subscribeTheme, currentTheme, () => "light");
  return <span ref={node => {
    if (!node || !mono) return;
    const ground = boxGroundColour(node);
    if (ground) node.style.setProperty("--sw-ground", ground);
  }} className={`sw-box loop${mono ? " mono" : ""} me-1.5 inline-block shrink-0 align-middle`} aria-hidden="true" style={{ width: size * 136 / 126, height: size }} dangerouslySetInnerHTML={{ __html: BOX }} />;
}

/**
 * The inline loading state for buttons, table rows and fields: the same box-opening artwork as
 * `LogoLoader`, 16-24px tall. A polite status announcing `label` (default "Loading"); the artwork is
 * hidden from assistive tech, `mono` draws it in the surrounding text colour (use inside buttons), never focusable, and still the open logo under reduced motion.
 */
export function BoxSpinner({ label, size = 20, className = "", mono = false }: { label?: string; size?: number; className?: string; mono?: boolean }) {
  return <span role="status" aria-label={label ?? t`Loading`} className={`sw-box-spinner inline-flex shrink-0 items-center align-middle ${className}`}>
    <BoxArt size={size} mono={mono} />
    <span className="sr-only">{label ?? t`Loading`}</span>
  </span>;
}
