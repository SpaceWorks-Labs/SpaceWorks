import { t } from "@lingui/core/macro";

/**
 * The one "how do I pay" line shown after a priced booking, registration or admission is
 * recorded. The server decides whether an online rail exists per charge, so the copy offers
 * both roads and the Payments page shows "Pay now" or "Pay at the space" for each charge.
 * `pending`: the request still waits for staff, so nothing is owed yet.
 */
export function PayNextStep({ paymentsHref, pending = false }: { paymentsHref: string; pending?: boolean }) {
  if (pending) return <p className="mt-3 text-sm text-muted">{t`You will only be charged if staff approve it.`}</p>;
  return <p className="mt-3 text-sm text-muted">
    {t`The charge is listed under `}<a className="font-semibold text-ink underline" href={paymentsHref}>{t`Payments`}</a>
    {t` in your member area. Pay online there when it is offered, or pay at the space.`}
  </p>;
}
