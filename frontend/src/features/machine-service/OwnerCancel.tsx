import { useQuery, type QueryKey } from "@tanstack/react-query";

import { getAccessToken } from "../../lib/api";
import { cancelOwnServiceRequest, fetchOwnerControls, serviceKeys } from "./api";
import { ServiceCancelButton } from "./ServiceCancelButton";

/** Cancel control on a tracking page, shown only to the signed-in OWNER of the job.
 *
 * Eligibility comes from the authenticated owner lookup (member surface), never from the
 * bearer token alone: anonymous visitors and non-owners simply see no control.
 */
export function OwnerCancel({ token, title, makerspaceSlug, extraKeys = [] }: {
  token: string; title: string; makerspaceSlug: string; extraKeys?: QueryKey[];
}) {
  const signedIn = Boolean(getAccessToken("member"));
  const owner = useQuery({ queryKey: serviceKeys.owner(token), queryFn: () => fetchOwnerControls(token),
    enabled: signedIn && Boolean(token), retry: false, staleTime: 0 });
  if (!owner.data?.can_cancel) return null;
  const requestId = owner.data.request_id;
  return <ServiceCancelButton title={title} onCancel={() => cancelOwnServiceRequest(requestId)}
    invalidate={[serviceKeys.status(token), serviceKeys.owner(token), ["member", makerspaceSlug, "activity"], ...extraKeys]} />;
}
