import { t } from "@lingui/core/macro";
import { useQuery, type QueryKey } from "@tanstack/react-query";
import { Link } from "react-router-dom";

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
  const owner = useOwner(token);
  if (!owner.data?.can_cancel) return null;
  const requestId = owner.data.request_id;
  return <ServiceCancelButton title={title} onCancel={() => cancelOwnServiceRequest(requestId)}
    invalidate={[serviceKeys.status(token), serviceKeys.owner(token), ["member", makerspaceSlug, "activity"], ...extraKeys]} />;
}

function useOwner(token: string) {
  const signedIn = Boolean(getAccessToken("person"));
  return useQuery({ queryKey: serviceKeys.owner(token), queryFn: () => fetchOwnerControls(token),
    enabled: signedIn && Boolean(token), retry: false, staleTime: 0 });
}

/** For the signed-in owner only: the job's page in the member area, where quotes and changes are answered. */
export function OwnerJobLink({ token, path }: { token: string; path: (part: string) => string }) {
  const owner = useOwner(token);
  if (!owner.data?.request_id) return null;
  return <Link className="desk-button" to={path(`member/machine-jobs/${owner.data.request_id}`)}>{t`Open in your member area`}</Link>;
}
