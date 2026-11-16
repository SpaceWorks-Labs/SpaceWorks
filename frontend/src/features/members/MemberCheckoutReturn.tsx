import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

/** How often, and how many times, the list is re-read while the provider's webhook lands. */
export const CHECKOUT_POLL_MS = 3000;
export const CHECKOUT_POLLS = 10;

/**
 * The landing for a hosted checkout's return (`?checkout=success|cancelled`, set by the server on
 * every Stripe/Razorpay page). It moves the payer to the Payments tab, says what happened, and
 * re-reads their charges and receipts for ~30 s: the charge only turns paid when the provider's
 * webhook arrives, and until then the row still reads "pending" -- without this note a payer who
 * has just paid sees their debt unchanged and may pay again.
 */
export function MemberCheckoutReturn({ onPaymentsTab = true }: { onPaymentsTab?: boolean }) {
  const [search, setSearch] = useSearchParams();
  const outcome = search.get("checkout");
  const location = useLocation();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [polls, setPolls] = useState(0);
  const known = outcome === "success" || outcome === "cancelled";

  useEffect(() => {
    if (!known || onPaymentsTab) return;
    const base = location.pathname.match(/^((?:\/m\/[^/]+)?\/member)(?:\/.*)?$/)?.[1];
    if (base) navigate(`${base}/payments?checkout=${outcome}`, { replace: true });
  }, [known, onPaymentsTab, outcome, location.pathname, navigate]);

  useEffect(() => {
    if (outcome !== "success" || !onPaymentsTab || polls >= CHECKOUT_POLLS) return;
    const timer = window.setTimeout(() => {
      void client.invalidateQueries({ predicate: (query) => query.queryKey[0] === "member" && query.queryKey.includes("payments") });
      void client.invalidateQueries({ queryKey: ["payment-documents"] });
      setPolls((count) => count + 1);
    }, CHECKOUT_POLL_MS);
    return () => window.clearTimeout(timer);
  }, [outcome, onPaymentsTab, polls, client]);

  if (!known || !onPaymentsTab) return null;
  const dismiss = () => setSearch((params) => { params.delete("checkout"); return params; }, { replace: true });
  return <div role="status" className={`desk-panel p-4 text-sm ${outcome === "success" ? "border-success" : "border-warn"}`}>
    <p className="text-ink">{outcome === "success"
      ? t`Thank you. Your payment is being confirmed by the provider and shows as paid here within a minute or two. Please don't pay again.`
      : t`Checkout was cancelled and nothing was charged. You can pay again below, or pay at the space.`}</p>
    <button type="button" className="desk-button-ghost mt-2" onClick={dismiss}>{t`Dismiss`}</button>
  </div>;
}
