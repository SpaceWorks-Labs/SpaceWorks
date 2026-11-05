import { useQuery } from "@tanstack/react-query";
import { fetchMe, refreshAccessToken } from "../../lib/api";
import { ANONYMOUS_READER, readerFromUser } from "./helpAudience";
import type { HelpReader } from "./helpTypes";

/**
 * Who is reading the guide. The guide is public, so a signed-out visitor simply reads the
 * everyone sections; a session (restored from the refresh cookie, as a new console tab does)
 * adds the staff sections the person's actions call for. `platform` reads the superadmin's
 * separate session, which the console's Help links ask for with `?context=platform`.
 */
export function useHelpReader(platform: boolean): { reader: HelpReader; loading: boolean } {
  const query = useQuery({
    queryKey: ["help", "reader", platform ? "platform" : "person"],
    queryFn: async () => {
      const context = platform ? "platform" : "person";
      const refreshed = await refreshAccessToken(context).catch(() => false);
      if (!refreshed) return null;
      return fetchMe(context).catch(() => null);
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
  return { reader: query.data ? readerFromUser(query.data) : ANONYMOUS_READER, loading: query.isLoading };
}
