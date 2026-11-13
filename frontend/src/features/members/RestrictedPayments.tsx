import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ThemeToggle } from "../../components/ThemeToggle";
import { EmptyState } from "../../components/ui";
import { LogoLoader } from "../../components/LogoLoader";
import { logout, memberRequest, StructuredApiError } from "../../lib/api";
import { MemberPaymentRows, type MemberPayment } from "./MemberPayments";
import { memberPaymentErrorText } from "./memberPaymentErrors";

export function isRestrictedAccount(error: unknown) {
  return error instanceof StructuredApiError && error.status === 401
    && ["account_restricted", "account_suspended"].includes(error.code ?? "");
}

/** Decision 260: a limited session has its own charges and sign-out, with no other portal tools. */
export function RestrictedPayments({ makerspaceId, name }: { makerspaceId: number; name: string }) {
  const client = useQueryClient();
  const [signOutError, setSignOutError] = useState(false);
  const base = `/member/makerspaces/${makerspaceId}/payments`;
  const key = ["member", "restricted-payments", makerspaceId];
  const payments = useQuery({ queryKey: key, enabled: makerspaceId >= 0, retry: false,
    queryFn: () => memberRequest<MemberPayment[]>(base) });
  const checkout = useMutation({
    mutationFn: (id: number) => memberRequest<{ checkout_url: string }>(`${base}/${id}/checkout`, { method: "POST" }),
    onSuccess: data => { window.location.assign(data.checkout_url); },
    onSettled: () => { void client.invalidateQueries({ queryKey: key }); },
  });
  const signOut = async () => {
    setSignOutError(false);
    try { await logout("person"); window.location.reload(); }
    catch { setSignOutError(true); client.clear(); }
  };
  return <main className="mx-auto grid w-full max-w-3xl gap-5 p-4 sm:p-6">
    <header className="flex min-w-0 flex-wrap items-center justify-between gap-3">
      <h1 className="title-page break-words">{t`Payments`} · {name}</h1>
      <div className="flex items-center gap-2"><ThemeToggle variant="icon" />
        <button className="desk-button" onClick={() => void signOut()}>{t`Sign out`}</button></div>
    </header>
    <p className="text-sm text-muted">{t`Your account is restricted. You can still view and pay your own charges. Contact the space for help with your access.`}</p>
    {makerspaceId < 0 ? <div role="alert"><p>{t`Couldn't load your makerspace. Try again.`}</p>
      <button className="desk-button mt-3" onClick={() => window.location.reload()}>{t`Retry`}</button></div>
      : payments.isLoading ? <LogoLoader label={t`Loading payments...`} size={48} />
      : payments.error ? <div role="alert"><p>{memberPaymentErrorText(payments.error)}</p>
        <button className="desk-button mt-3" onClick={() => void payments.refetch()}>{t`Retry`}</button></div>
      : payments.data?.length ? <MemberPaymentRows makerspaceId={makerspaceId} payments={payments.data} refunds
        checkoutPaymentId={checkout.isPending ? checkout.variables : undefined} onCheckout={id => checkout.mutate(id)} />
      : <EmptyState message={t`Nothing to pay. You are all settled.`} />}
    {checkout.error ? <p role="alert" className="text-sm text-danger">{memberPaymentErrorText(checkout.error)}</p> : null}
    {signOutError ? <p role="alert" className="text-sm text-danger">{t`Couldn't sign out. Try again.`}</p> : null}
  </main>;
}
