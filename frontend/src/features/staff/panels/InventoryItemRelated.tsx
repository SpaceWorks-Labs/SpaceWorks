import { t } from "@lingui/core/macro";

import { ListRow, StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { STATUS_LABELS, statusTone } from "../../incidents/api";
import { openLinks, RelatedLinks, type RelatedCandidate } from "../crossLinks/RelatedLinks";
import { useCrossLink } from "../crossLinks/staffHref";
import { useSubjectIncidents } from "../crossLinks/subjectIncidents";
import type { AdminProduct } from "./InventoryPanelShared";

/**
 * IN6: what else touches this item. Who holds it now (the ledger), its requests, repairs,
 * To-Buy and incidents, each opened in that area's own list and offered only when the viewer
 * can open that area (decision 224). Incidents load inline because they are the one thing a
 * lending manager must not miss here.
 */
export function InventoryItemRelated({ product, makerspaceId }: { product: AdminProduct; makerspaceId: number }) {
  const link = useCrossLink();
  const incidents = useSubjectIncidents(makerspaceId, "product", product.id);
  const out = product.issued_quantity;
  const candidates: RelatedCandidate[] = [
    { key: "ledger", label: t`Who has it now`, helper: t`Current holders in the ledger`, count: out, href: link("ledger", { q: product.name }) },
    { key: "requests", label: t`Requests`, helper: t`Loan requests that include this item`, href: link("requests", { search: product.name }) },
    { key: "needsfix", label: t`Repair shelf`, helper: t`Damaged units and repairs`, count: product.damaged_quantity, href: link("needsfix") },
    { key: "tobuy", label: t`To-Buy`, helper: t`Restock and replacement orders`, href: link("tobuy") },
    ...(!incidents.hidden ? [{ key: "incidents", label: t`Incidents`, helper: t`Reported against this item`, count: incidents.count, href: link("incidents", { product: product.id }) }] : []),
  ];
  const links = openLinks(candidates);
  return <div className="grid min-w-0 gap-6">
    <RelatedLinks links={links} empty={t`Nothing else is linked to this item that you can open.`} />
    {!incidents.hidden && incidents.rows.length ? <section className="grid gap-2" aria-label={t`Recent incidents`}>
      <h3 className="title-section">{t`Recent incidents`}</h3>
      {incidents.rows.slice(0, 3).map(row => <ListRow key={row.id} title={row.title} href={link("incidents", { incident: row.id })}
        meta={formatDate(row.occurred_at)} right={<StatusPill tone={statusTone(row.status)} label={STATUS_LABELS[row.status]} />} />)}
    </section> : null}
  </div>;
}
