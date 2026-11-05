import type { QueryState } from "../../components/ui/types";
import { StructuredApiError, isSurfaceOff } from "../../lib/api";

type Copy = { noun: string; missing?: string };

/**
 * Public pages say *why* a load failed, as they did before the revamp, and offer Retry only where a
 * retry can help: a throttle or an outage can clear, a switched-off module or a missing page cannot.
 */
export function publicErrorState(error: unknown, { noun, missing }: Copy, onRetry: () => void): QueryState {
  const apiError = error instanceof StructuredApiError ? error : null;
  if (apiError?.status === 429) return { status: "error", error: "Please slow down. Too many requests were made; wait a moment and retry.", onRetry };
  // A switched-off module answers a typed 404 (#183B): say so, not "not found".
  if (isSurfaceOff(error)) return { status: "error", error: `${noun} ${noun.endsWith("s") ? "aren't" : "isn't"} turned on at this makerspace.` };
  if (apiError?.status === 404) return { status: "error", error: missing ?? "We couldn't find this makerspace. Check the link." };
  return { status: "error", error: apiError?.detail || `Couldn't load ${noun.toLowerCase()}. Try again.`, onRetry };
}
