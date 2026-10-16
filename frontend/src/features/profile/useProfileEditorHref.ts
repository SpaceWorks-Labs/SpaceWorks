import { useQuery, useQueryClient } from "@tanstack/react-query";
import { bootstrapTenant, memberRequest, tenantMemberRequest, StructuredApiError } from "../../lib/api";
import type { MemberProfile } from "../members/memberProfile/types";
import { personalRecipientKey } from "../notifications/personalQueryKeys";
import { memberProfileKey } from "./edit/profileEditApi";

const editorPath = "/member/account-portal?section=profile";
type Memberships = { memberships: { makerspace: { slug: string }; membership_status: string }[] };

/** Ownership comes from the public response; these authenticated reads only locate its editor.
 * The central URL has no tenant, and a person's handle belongs to one membership's profile. */
export function useProfileEditorHref(handle: string, owner: boolean, singleTenant: boolean) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["public-profile-editor", handle, personalRecipientKey()],
    enabled: owner && !singleTenant,
    retry: false,
    queryFn: async () => {
      const own = await memberRequest<Memberships>("/memberships/me");
      for (const membership of own.memberships.filter(row => row.membership_status === "active")) {
        const slug = membership.makerspace.slug;
        try {
          // Discovery caches credentials without switching the public page's active tenant.
          // Reuse the member portal's caches when arriving from an editor.
          const bootstrap = await client.fetchQuery({ queryKey: ["member", slug, "bootstrap"],
            queryFn: () => bootstrapTenant({ slug }, { activate: false }), staleTime: 60_000 });
          if (!bootstrap.modules.includes("membership")) continue;
          const id = bootstrap.makerspace.id;
          const profile = await client.fetchQuery({ queryKey: memberProfileKey(id),
            queryFn: () => tenantMemberRequest<MemberProfile>(slug, `/member/makerspaces/${id}/profile`), staleTime: 60_000 });
          if (profile.handle === handle) return `/m/${encodeURIComponent(slug)}${editorPath}`;
        } catch (error) {
          // A membership can stop being servable between the list and the profile read.
          if (error instanceof StructuredApiError && [400, 403, 404].includes(error.status)) continue;
          throw error;
        }
      }
      return null;
    },
  });
  return { ...query, href: owner ? singleTenant ? editorPath : query.data ?? undefined : undefined };
}
