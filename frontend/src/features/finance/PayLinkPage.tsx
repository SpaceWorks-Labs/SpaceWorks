import { t } from "@lingui/core/macro";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import { StructuredApiError } from "../../lib/api";
import { OfflinePayment, type OfflineCollection } from "../members/MemberPaymentOffline";
import { payLinkRequest } from "./financeApi";

type PayLink = OfflineCollection & {
  makerspace: string; label: string; amount: string; currency: string; status: string; expires_at: string;
  online_available: boolean;
};

/** A pay link: what is owed and to whom, never who owes it. Pay online or tell the space you paid. */
export function PayLinkPage() {
  const { token = "" } = useParams();
  const link = useQuery({ queryKey: ["pay-link", token], queryFn: () => payLinkRequest<PayLink>(encodeURIComponent(token)),
    retry: false, enabled: token !== "complete" });
  const checkout = useMutation({
    mutationFn: () => payLinkRequest<{ checkout_url: string }>(`${encodeURIComponent(token)}/checkout`, { method: "POST" }),
    onSuccess: data => { window.location.assign(data.checkout_url); },
  });
  const claim = useMutation({
    mutationFn: (body: { reference: string; paid_on: string }) =>
      payLinkRequest(`${encodeURIComponent(token)}/claim`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { void link.refetch(); },
  });
  if (token === "complete") {
    return <CenteredCardLayout media={{ icon: "CheckCircle", tone: "success" }} title={t`Thank you`}
      body={t`Your payment is being confirmed by the provider. You can close this page.`}
      primary={{ label: t`Close`, onClick: () => window.close() }} state={{ status: "ready" }} />;
  }
  const gone = link.error instanceof StructuredApiError && link.error.status === 404;
  if (gone) {
    return <CenteredCardLayout media={{ icon: "CircleAlert", tone: "warn" }} title={t`This payment link has expired`}
      body={t`Ask the space for a new link.`} primary={{ label: t`Go home`, href: "/" }} state={{ status: "ready" }} />;
  }
  const data = link.data;
  const paid = data && data.status !== "pending";
  return <CenteredCardLayout eyebrow={data?.makerspace} title={data ? t`Pay ${data.currency.toUpperCase()} ${data.amount}` : t`Payment`}
    state={link.isLoading ? { status: "loading" } : link.error ? { status: "error", error: t`Couldn't open this link.`,
      onRetry: () => { void link.refetch(); } } : { status: "ready" }}
    body={data ? <p>{paid ? t`This charge is already settled. Nothing more to pay.` : t`For ${data.label}.`}</p> : null}
    content={data && !paid ? <OfflinePayment offline={data} onClaim={body => claim.mutate(body)} pending={claim.isPending}
      error={claim.error} /> : null}
    primary={data?.online_available && !paid
      ? { label: t`Pay online`, onClick: () => checkout.mutate(), pending: checkout.isPending, pendingLabel: "Opening checkout…" }
      : { label: t`Done`, href: "/" }}
    footer={checkout.error ? <p role="alert" className="text-sm text-danger">{t`Online payment isn't available right now. Try again or pay offline.`}</p> : null}
  />;
}
