import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { Card } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { DonationShell } from "./DonationShell";
import { donationKeys, donationsApi, type PledgeAction } from "./donationsApi";
import { PledgeCard } from "./PledgeCard";

/** A guest's own pledge, managed from the signed link they were given. */
export function GuestPledgePage() {
  const { token = "" } = useParams();
  const client = useQueryClient();
  const pledge = useQuery({ queryKey: donationKeys.pledge(token), queryFn: () => donationsApi.guestPledge(token),
    retry: false, enabled: Boolean(token) });
  const change = useMutation({
    mutationFn: (body: PledgeAction) => donationsApi.changeGuestPledge(token, body),
    onSuccess: result => client.setQueryData(donationKeys.pledge(token), result),
  });
  if (pledge.error instanceof StructuredApiError && pledge.error.status === 404) {
    return <DonationShell title={t`Your pledge`} state={{ status: "ready" }}>
      <Card><p className="text-sm">{t`This link isn't valid any more. Check the latest email from the space.`}</p></Card>
    </DonationShell>;
  }
  const state = pledge.isLoading ? { status: "loading" as const } : pledge.error ? { status: "error" as const,
    error: t`Couldn't load your pledge.`, onRetry: () => { void pledge.refetch(); } } : { status: "ready" as const };
  return <DonationShell title={t`Your pledge`} state={state}>
    {pledge.data ? <div className="grid gap-3">
      <PledgeCard key={`${pledge.data.amount}-${pledge.data.interval}`} pledge={pledge.data}
        onAction={body => change.mutate(body)} pending={change.isPending} error={change.error} />
      <p className="text-xs text-muted">{t`Keep this link private: anyone with it can change this pledge.`}</p>
    </div> : null}
  </DonationShell>;
}
