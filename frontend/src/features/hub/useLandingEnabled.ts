import { useQuery } from "@tanstack/react-query";
import { publicV1Request } from "../../lib/api";

// Typed locally until the staging step regenerates `generated/api.ts` (`landing_enabled` on PublicConfig).
type LandingConfig = { landing_enabled?: boolean };

/**
 * Decision 300(b): the deployment's `HUB_LANDING_ENABLED` switch, read from the existing public
 * config. `enabled` is undefined while the answer is loading so the front page never flashes the
 * landing before an opt-out arrives. A failed or older config (no field) means the default: on.
 */
export function useLandingEnabled(): { loading: boolean; enabled: boolean } {
  const query = useQuery({
    queryKey: ["public-config", "landing"],
    queryFn: () => publicV1Request<LandingConfig>("/config"),
    staleTime: 5 * 60_000,
    retry: false,
  });
  return { loading: query.isPending, enabled: query.data?.landing_enabled !== false };
}
