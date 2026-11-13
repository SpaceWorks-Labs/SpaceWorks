import type { QueryClient } from "@tanstack/react-query";

/** Organization actions can reach every linked venue and every staff domain. */
export async function refreshOrganizationAuthority(client: QueryClient) {
  // Recompute the real session first, so refreshed data and navigation use the
  // new authority. Inactive queries are marked stale for their next mount too.
  await client.invalidateQueries({ queryKey: ["staff", "me"] });
  await client.invalidateQueries({
    predicate: ({ queryKey }) => !(queryKey[0] === "staff" && queryKey[1] === "me"),
  });
}
