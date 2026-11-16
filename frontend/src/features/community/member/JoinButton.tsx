import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";

import { guestErrorText } from "../../guestPasses/api";
import { communityMemberApi } from "../api";

/** Where the member area's own membership request form sits (MemberArea overview). */
export const JOIN_ANCHOR = "join-membership";

/**
 * The "Join" call to action (decision 223 k, membership.join_funnel): checks the event ticket or guest
 * pass with `join-prefill`, then hands over to the ordinary membership request — vouching, forms and
 * payment stay the admission path's. `memberHref` is the member area, where that form lives.
 */
export function JoinButton({ makerspaceId, source, memberHref }: {
  makerspaceId: number; source: { registration_id: number } | { guest_pass_id: number }; memberHref: string;
}) {
  const prefill = useMutation({
    mutationFn: () => communityMemberApi.joinPrefill(makerspaceId, source),
    onSuccess: () => {
      const form = document.getElementById(JOIN_ANCHOR);
      if (form) form.scrollIntoView({ behavior: "smooth", block: "start" });
    },
  });
  const onPage = typeof document !== "undefined" && Boolean(document.getElementById(JOIN_ANCHOR));
  return <div className="grid gap-2">
    {!prefill.data ? <div><button type="button" className="desk-button-brand min-h-11" disabled={prefill.isPending} onClick={() => prefill.mutate()}>
      {prefill.isPending ? t`Checking…` : t`Join as a member`}</button></div> : <div role="status" className="grid gap-2 text-sm">
      <p className="text-ink">{t`You'll apply as ${prefill.data.name || prefill.data.email}${prefill.data.email && prefill.data.name ? ` (${prefill.data.email})` : ""}, after your ${prefill.data.source_label.toLowerCase()}.`}</p>
      {onPage ? <p className="text-muted">{t`Fill in the membership request on this page to finish.`}</p>
        : <div><a className="desk-button-brand inline-flex min-h-11 items-center" href={`${memberHref}#${JOIN_ANCHOR}`}>{t`Continue to the membership request`}</a></div>}
    </div>}
    {prefill.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(prefill.error)}</p> : null}
  </div>;
}
