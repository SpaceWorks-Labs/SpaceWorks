import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../../components/layouts";
import { ErrorText } from "../../../components/ui";
import { getAccessToken, refreshAccessToken, StructuredApiError } from "../../../lib/api";
import { useChargesOn } from "../../../lib/charges";
import { useTenantPath } from "../../../lib/tenant";
import { MemberAuthPanel } from "../../members/MemberAuthPanel";
import { useMemberSpace } from "./MemberOrdersPage";
import { buySeriesPass, listSeriesPasses, safeCheckoutUrl, type PassType } from "./ticketingMemberApi";

function price(amount: string) {
  return Number(amount) ? amount : "Free";
}

function errorMessage(error: unknown) {
  if (error instanceof StructuredApiError) return error.detail ?? error.message;
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}

/** Release 2 L6 (X41): buy one pass that covers every upcoming public occurrence of a series. */
export function MemberSeriesPassPage() {
  const { seriesId = "" } = useParams();
  const space = useMemberSpace();
  const tenantPath = useTenantPath(space.makerspaceSlug);
  const chargesOn = useChargesOn("events", space.makerspaceSlug); // #184: a free events domain shows no pass price
  const navigate = useNavigate();
  const [restoring, setRestoring] = useState(!getAccessToken());
  useEffect(() => { if (restoring) refreshAccessToken().finally(() => setRestoring(false)); }, []);
  const id = /^\d+$/.test(seriesId) ? Number(seriesId) : 0;
  const passes = useQuery({ queryKey: ["member-series-passes", space.makerspaceId, id], retry: false,
    enabled: !restoring && Boolean(space.makerspaceId && id), queryFn: () => listSeriesPasses(space.makerspaceId, id) });
  const [choice, setChoice] = useState(0);
  const buy = useMutation({ mutationFn: (passTypeId: number) => buySeriesPass(space.makerspaceId, id, passTypeId),
    onSuccess: result => {
      const checkout = safeCheckoutUrl(result.checkout_url);
      if (checkout) window.location.assign(checkout);
      else navigate(tenantPath(`member/orders/${result.order.id}`));
    } });
  const error = passes.error;
  if (error instanceof StructuredApiError && error.status === 401) {
    return <MemberAuthPanel makerspaceSlug={space.makerspaceSlug} onAuthenticated={() => { void passes.refetch(); }} />;
  }
  const offSale = (error instanceof StructuredApiError && [400, 404].includes(error.status)) || !id;
  const rows: PassType[] = (passes.data ?? []).filter(row => row.is_active);
  const selected = choice || rows[0]?.id || 0;
  return <CenteredCardLayout width={480} eyebrow="Series pass" title="Buy a series pass"
    state={restoring || space.loading || passes.isLoading ? { status: "loading" } : { status: "ready" }}
    body={offSale || (!error && passes.data && !rows.length) ? "Passes for this series are not on sale."
      : "One pass gives you a place at every upcoming public date of this series."}
    content={<div className="grid gap-3">
      {error && !offSale ? <ErrorText message={errorMessage(error)} /> : null}
      {rows.length ? <fieldset className="grid gap-2"><legend className="mb-1 text-sm font-semibold text-ink">Choose a pass</legend>
        {rows.map(row => <label key={row.id} className="flex min-h-11 items-start gap-3 rounded-card border border-line p-3 text-sm text-ink">
          <input type="radio" name="pass" value={row.id} checked={selected === row.id} onChange={() => setChoice(row.id)} />
          <span className="grid gap-0.5"><span className="font-semibold">{row.name}</span>
            <span className="text-muted">{chargesOn ? price(row.amount) : "Free"}{row.sales_end_at ? ` · on sale until ${new Date(row.sales_end_at).toLocaleString()}` : ""}</span></span>
        </label>)}
      </fieldset> : null}
      {buy.error ? <ErrorText message={errorMessage(buy.error)} /> : null}
    </div>}
    primary={{ label: buy.isPending ? "Working…" : "Buy this pass", onClick: () => buy.mutate(selected),
      disabled: !selected || buy.isPending, disabledReason: "Choose a pass first." }}
    escape={{ label: "All events", href: tenantPath("events") }} />;
}
