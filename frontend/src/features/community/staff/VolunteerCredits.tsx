import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { guestErrorText } from "../../guestPasses/api";
import { MembershipPagination } from "../../staff/MembershipPagination";
import { communityKeys, communityStaffApi } from "../api";
import { creditLabel, creditStatusLabel, hoursLabel } from "../labels";
import { LogoLoader } from "../../../components/LogoLoader";

/** Credits earned from approved hours. Only an unused credit can be voided; an applied one is history. */
export function VolunteerCredits({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const credits = useQuery({ queryKey: communityKeys.credits(makerspaceId, page), queryFn: () => communityStaffApi.credits(makerspaceId, page) });
  const voidCredit = useMutation({ mutationFn: (id: number) => communityStaffApi.voidCredit(makerspaceId, id),
    onSuccess: () => client.invalidateQueries({ queryKey: communityKeys.all(makerspaceId) }) });
  const rows = credits.data?.results ?? [];
  return <section aria-labelledby="volunteer-credits-title" className="grid gap-3">
    <h3 id="volunteer-credits-title" className="title-section">{t`Volunteer credits`}</h3>
    {credits.isLoading ? <LogoLoader label={t`Loading credits…`} size={48} className="min-h-16 py-3" /> : null}
    {credits.isError ? <p role="alert" className="text-sm text-danger">{guestErrorText(credits.error)}</p> : null}
    {credits.isSuccess && !rows.length ? <EmptyState message={t`No credits earned yet.`} /> : null}
    <ul className="grid gap-2">
      {rows.map((row) => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-control border border-line p-3 text-sm">
        <span className="min-w-0 flex-1 basis-48 text-ink">{row.member_name || t`Member #${row.member}`} · {creditLabel(row)}
          <span className="text-muted"> · {t`from ${hoursLabel(row.minutes_converted)}`} · {formatDate(row.created_at)}</span></span>
        <StatusPill tone={row.status === "available" ? "success" : "neutral"} label={creditStatusLabel(row.status)} />
        {row.status === "available" ? <button type="button" className="desk-button-ghost min-h-11" disabled={voidCredit.isPending} onClick={() => voidCredit.mutate(row.id)}>{t`Void`}</button> : null}
      </li>)}
    </ul>
    {voidCredit.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(voidCredit.error)}</p> : null}
    <MembershipPagination label="credits" page={page} next={credits.data?.next} previous={credits.data?.previous} fetching={credits.isFetching} onPage={setPage} />
  </section>;
}
