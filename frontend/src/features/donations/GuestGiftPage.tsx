import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { Card } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { DonationShell } from "./DonationShell";
import { donationKeys, donationsApi, giveError } from "./donationsApi";
import { GiftStatusView } from "./GiftStatusView";
import { GuestPaidClaim } from "./GuestPaidClaim";

/** A guest's own gift, reached only by the signed link they were given (or emailed with the receipt). */
export function GuestGiftPage() {
  const { token = "" } = useParams();
  const client = useQueryClient();
  const gift = useQuery({ queryKey: donationKeys.gift(token), queryFn: () => donationsApi.gift(token), retry: false,
    enabled: Boolean(token) });
  const pay = useMutation({
    mutationFn: () => donationsApi.checkout(token),
    onSuccess: result => {
      if (result.checkout_url) window.location.assign(result.checkout_url);
      else client.setQueryData(donationKeys.gift(token), result);
    },
  });
  if (gift.error instanceof StructuredApiError && gift.error.status === 404) {
    return <DonationShell title="Your gift" state={{ status: "ready" }}>
      <Card><p className="text-sm">This link isn't valid any more. Check the latest email from the space.</p></Card>
    </DonationShell>;
  }
  const state = gift.isLoading ? { status: "loading" as const } : gift.error ? { status: "error" as const,
    error: "Couldn't load your gift.", onRetry: () => { void gift.refetch(); } } : { status: "ready" as const };
  return <DonationShell title="Your gift" state={state}>
    {gift.data ? <div className="grid gap-3">
      <GiftStatusView gift={gift.data} taxReceiptHref={donationsApi.taxReceiptUrl(token)} onPayOnline={() => pay.mutate()}
        paying={pay.isPending} />
      {gift.data.status === "pending" && gift.data.offline?.claimable ? <GuestPaidClaim token={token} /> : null}
      {pay.error ? <p role="alert" className="text-sm text-danger">Online payment isn't available right now. Pay offline, or try
        again later. ({giveError(pay.error)})</p> : null}
      <p className="text-xs text-muted">Keep this link private: anyone with it can see this gift.</p>
    </div> : null}
  </DonationShell>;
}
