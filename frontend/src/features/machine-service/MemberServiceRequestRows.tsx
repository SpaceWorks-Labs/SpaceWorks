import { Link } from "react-router-dom";

import { EmptyState, ListRow, StatusPill } from "../../components/ui";
import { useTenantPath } from "../../lib/tenant";
import { cancelOwnServiceRequest } from "./api";
import { ServiceCancelButton } from "./ServiceCancelButton";
import { ServiceRequestEta } from "./ServiceRequestEta";
import type { ServiceRequestEta as Eta } from "./types";
import { serviceStatusLabel, serviceStatusTone } from "./types";

/** The member's own machine-service row as served by the private activity endpoint. */
export type MemberServiceRequest = {
  request_id?: number; can_cancel?: boolean; public_token?: string;
  machine_type?: string; machine_type_name?: string; title: string; status: string;
  queue_position: number | null; eta?: Eta | null;
};

export function MemberServiceRequestRows({ rows, makerspaceSlug }: { rows: MemberServiceRequest[]; makerspaceSlug: string }) {
  const tenantPath = useTenantPath(makerspaceSlug);
  if (!rows.length) return <EmptyState message="Nothing here yet. Check back after your next visit." />;
  return <>{rows.map((item, index) => <ListRow key={item.request_id ?? `${item.title}-${index}`} title={item.title}
    meta={item.eta ? <ServiceRequestEta eta={item.eta} status={item.status} compact />
      : item.queue_position ? `Queue ${item.queue_position}` : undefined}
    right={<div className="grid justify-items-start gap-2">
      <StatusPill label={serviceStatusLabel(item.status)} tone={serviceStatusTone(item.status)} />
      {item.public_token ? <Link className="desk-button-ghost" to={tenantPath(`machine-service/requests/${item.public_token}`)}>Track job</Link> : null}
      {item.can_cancel && item.request_id ? <ServiceCancelButton title={item.title}
        onCancel={() => cancelOwnServiceRequest(item.request_id!)}
        invalidate={[["member", makerspaceSlug, "activity"], ["public-machine-service-status"], ["public-printer-status"]]} /> : null}
    </div>} />)}</>;
}
