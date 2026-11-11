import { t } from "@lingui/core/macro";
import type { QueryState } from "../../components/ui/types";
import { StructuredApiError, isSurfaceOff } from "../../lib/api";

type Surface = "bookings" | "events" | "machines" | "stats";
type Copy = { surface: Surface; missing?: string };

// Whole sentences per surface, so a translator never has to inflect a borrowed noun.
function surfaceCopy(surface: Surface) {
  switch (surface) {
    case "bookings": return { off: t`Bookings aren't turned on at this makerspace.`, failed: t`Couldn't load bookings. Try again.` };
    case "events": return { off: t`Events aren't turned on at this makerspace.`, failed: t`Couldn't load events. Try again.` };
    case "machines": return { off: t`Machines aren't turned on at this makerspace.`, failed: t`Couldn't load machines. Try again.` };
    case "stats": return { off: t`Public stats aren't turned on at this makerspace.`, failed: t`Couldn't load public stats. Try again.` };
  }
}

/**
 * Public pages say *why* a load failed, as they did before the revamp, and offer Retry only where a
 * retry can help: a throttle or an outage can clear, a switched-off module or a missing page cannot.
 */
export function publicErrorState(error: unknown, { surface, missing }: Copy, onRetry: () => void): QueryState {
  const copy = surfaceCopy(surface);
  const apiError = error instanceof StructuredApiError ? error : null;
  if (apiError?.status === 429) return { status: "error", error: t`Please slow down. Too many requests were made; wait a moment and retry.`, onRetry };
  // A switched-off module answers a typed 404 (#183B): say so, not "not found".
  if (isSurfaceOff(error)) return { status: "error", error: copy.off };
  if (apiError?.status === 404) return { status: "error", error: missing ?? t`We couldn't find this makerspace. Check the link.` };
  return { status: "error", error: apiError?.detail || copy.failed, onRetry };
}
