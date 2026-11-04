import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import type { AuthUserPayload } from "../../generated/api";
import { ErrorBlock } from "../../components/ui";
import { sessionScope } from "./eventProgramme/sessionScope";
import { PayoutDashboard, PayoutQueue, PayoutDetail } from "../finance/eventPayouts";

/**
 * The core event-payout ledger under the payments tab. It needs VIEW_FINANCE on a live host
 * and nothing else: retained obligations stay readable and settleable with Events, the
 * reimbursement add-on or the payment rail switched off. Payouts are recorded, never sent.
 */
export function EventPayoutsSection({ makerspaceId }: { makerspaceId: number }) {
  const account = useQuery({ queryKey: ["event-payouts-actor", ...sessionScope()], queryFn: () => staffRequest<AuthUserPayload>("/auth/me"),
    gcTime: 0, retry: false });
  const [selected, setSelected] = useState<string | null>(null);
  if (account.error) return <ErrorBlock error={account.error} />;
  if (!account.data) return <p role="status">Loading event payouts…</p>;
  const scope = { actorId: account.data.id, makerspaceId };
  return <section className="mt-8 grid gap-6" aria-label="Event reimbursement payouts">
    {selected ? <>
      <button type="button" className="desk-button justify-self-start" onClick={() => setSelected(null)}>All event payouts</button>
      <PayoutDetail key={selected} scope={scope} id={selected} />
    </> : <>
      <PayoutDashboard scope={scope} />
      <PayoutQueue scope={scope} onOpen={setSelected} />
    </>}
  </section>;
}
