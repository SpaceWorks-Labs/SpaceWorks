import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PublicLayout, CenteredCardLayout } from "../../components/layouts";
import { EmptyState, StatusPill } from "../../components/ui";

import type { ArchivedPaymentSummary } from "../../generated/api";
import { StructuredApiError, staffRequest } from "../../lib/api";
import { MemberAuthPanel } from "./MemberAuthPanel";
import { MemberPaymentRows, type MemberPayment } from "./MemberPayments";

const MAKERSPACE_TONES = ["border-accent", "border-brand", "border-success", "border-warn"] as const;

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unable to load archived payments.";
}

function ArchivedMakerspacePayments({ summary }: { summary: ArchivedPaymentSummary }) {
  const queryClient = useQueryClient();
  const payments = useQuery({
    queryKey: ["member", "archived-payments", summary.makerspace.id, "payments"],
    queryFn: () => staffRequest<MemberPayment[]>(
      `/member/makerspaces/${summary.makerspace.id}/payments`,
    ),
    retry: false,
  });
  const checkout = useMutation({
    mutationFn: (paymentId: number) => staffRequest<{ checkout_url: string }>(
      `/member/makerspaces/${summary.makerspace.id}/payments/${paymentId}/checkout`,
      { method: "POST" },
    ),
    onSuccess: ({ checkout_url }) => {
      void queryClient.invalidateQueries({
        queryKey: ["member", "archived-payments", summary.makerspace.id, "payments"],
      });
      window.location.assign(checkout_url);
    },
  });

  return (
    <section className={`desk-panel ${MAKERSPACE_TONES[summary.makerspace.id % MAKERSPACE_TONES.length]} p-5`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-prose">
          <h2 className="title-panel break-words">{summary.makerspace.name}</h2>
          <p className="mt-1 text-sm text-muted">
            This makerspace is closed. Outstanding charges can still be settled and receipts remain readable here.
          </p>
        </div>
        <StatusPill label={`${summary.pending_count} pending / ${summary.total_count} total`} tone={summary.pending_count ? "warn" : "neutral"} />
      </div>
      {payments.isLoading ? (
        <p className="mt-4 text-sm text-muted">Loading payment history…</p>
      ) : null}
      {payments.isError ? (
        <p className="mt-4 text-sm text-danger" role="alert">
          {errorMessage(payments.error)}
        </p>
      ) : null}
      {payments.data ? (
        <MemberPaymentRows
          makerspaceId={summary.makerspace.id}
          payments={payments.data}
          checkoutPaymentId={checkout.isPending ? checkout.variables : undefined}
          onCheckout={(paymentId) => checkout.mutate(paymentId)}
        />
      ) : null}
      {checkout.isError ? (
        <p className="mt-3 text-sm text-danger" role="alert">
          {errorMessage(checkout.error)}
        </p>
      ) : null}
    </section>
  );
}

export function ArchivedPayments() {
  const queryClient = useQueryClient();
  const discovery = useQuery({
    queryKey: ["member", "archived-payments"],
    queryFn: () => staffRequest<ArchivedPaymentSummary[]>("/member/archived-payments"),
    retry: false,
  });
  const unauthenticated = discovery.error instanceof StructuredApiError
    && discovery.error.status === 401;
  // `payments` is a separable app. On a deployment that tombstones it the endpoint is
  // spliced out entirely, so this route must read as absent rather than as a permanent
  // error -- and it cannot ask tenant bootstrap which modules exist, because not depending
  // on bootstrap is the whole reason this route exists. The 404 IS the availability signal.
  const removed = discovery.error instanceof StructuredApiError
    && discovery.error.status === 404;

  if (removed) return <CenteredCardLayout title="Page not found" body="This page is unavailable on this deployment." primary={{ label: "Back to Space Works", href: "/" }} state={{ status: "ready" }} />;

  if (unauthenticated) {
    return (
      <MemberAuthPanel
        onAuthenticated={() => {
          void queryClient.invalidateQueries({
            queryKey: ["member", "archived-payments"],
          });
        }}
      />
    );
  }

  return <PublicLayout state={discovery.isLoading ? { status: "loading" } : discovery.isError ? { status: "error", error: errorMessage(discovery.error), onRetry: () => void discovery.refetch() } : { status: "ready" }}
    makerspace={{ name: "Space Works", slug: "", homeHref: "/" }} nav={[]} headerAction={{ label: "Member area", href: "/member" }}
    header={{ title: "Payments and receipts", eyebrow: "Archived makerspaces", subtitle: "Closed makerspaces no longer appear in the normal member area. Outstanding charges and past receipts remain available here.", primary: { label: "Back to Space Works", href: "/" } }} footer={{ links: [] }}>
    <div className="grid gap-6">{discovery.data?.length === 0 ? <EmptyState message="No charges outstanding from closed makerspaces." /> : discovery.data?.map(summary => <ArchivedMakerspacePayments key={summary.makerspace.id} summary={summary} />)}</div>
  </PublicLayout>;
}
