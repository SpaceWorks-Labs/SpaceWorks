import { Wallet } from "lucide-react";
import { DashboardLayout } from "../../../components/layouts";
import { usePayoutDashboard } from "./api";
import { money } from "./format";
import type { FinanceScope } from "./types";

export function PayoutDashboard({ scope }: { scope: FinanceScope }) {
  const query = usePayoutDashboard(scope);
  return <DashboardLayout header={{ eyebrow: "Finance", title: "Event reimbursements", subtitle: "Budgets, claims and recorded payouts, separated by currency." }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready",
      error: "The finance dashboard could not be loaded.", onRetry: () => { void query.refetch(); } }}
    stats={[]} main={[{ title: "Currency balances", empty: { message: "No reimbursement balances yet." },
      isEmpty: query.data?.currencies.length === 0, content: <div className="grid gap-6">
        {query.data?.pool_provider_available === false ? <p className="text-sm text-muted">Event budget information is unavailable. Core payout balances remain available.</p> : null}
        {query.data?.currencies.map(row => <article key={row.currency} className="grid gap-4 rounded-2xl border border-line bg-panel p-5">
          <h3 className="flex items-center gap-2 font-semibold"><Wallet aria-hidden="true" size={20} />{row.currency}</h3>
          <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {[["Pool", row.pool_minor], ["Awarded", row.awarded_minor], ["Claimed", row.claimed_minor],
              ["Approved", row.approved_minor], ["Recorded paid", row.paid_minor], ["Awaiting payout", row.awaiting_payout_minor]].map(([label, value]) =>
              <div key={String(label)}><dt className="text-sm text-muted">{label}</dt><dd className="text-lg font-semibold tabular-nums">{money(value as number | null, row.currency)}</dd></div>)}
          </dl>
          <p>{row.awaiting_payout_count ?? "Unavailable"} obligations awaiting payout</p>
          <h4 className="font-semibold">Claim ageing</h4>
          {row.claim_ageing == null ? <p className="text-sm text-muted">Claim ageing is unavailable.</p> : <ul className="grid gap-2">
            {row.claim_ageing.map(bucket => <li key={bucket.label} className="flex flex-wrap justify-between gap-2 border-t border-line pt-2">
              <span>{bucket.label}</span><span>{bucket.count} claims · {money(bucket.amount_minor, row.currency)}</span>
            </li>)}</ul>}
        </article>)}
      </div> }]} />;
}
