import { CenteredCardLayout } from "../../components/layouts";
import type { Action } from "../../components/ui";

export const PAUSED_TITLE = "This space is paused";
export const GENERIC_PAUSE_REASON = "This space is paused by the platform operator.";

/**
 * What every surface of a suspended space shows instead of its content: the generic reason only (the
 * operator's private reason never reaches members or staff), and a way out.
 */
export function PausedSpacePage({ name, reason, primary, escape }: { name?: string; reason?: string; primary: Action; escape?: Action }) {
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "CircleSlash", tone: "neutral" }} eyebrow={name}
    title={PAUSED_TITLE} body={<>
      <p>{reason || GENERIC_PAUSE_REASON}</p>
      <p className="mt-2">Nothing here is deleted. Check back later, or contact the space if you need something urgently.</p>
    </>} primary={primary} escape={escape} />;
}
