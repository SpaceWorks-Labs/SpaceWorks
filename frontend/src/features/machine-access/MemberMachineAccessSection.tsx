import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { StructuredApiError } from "../../lib/api";
import { getMachines } from "../staff/machinesApi";
import { accessKeys, listAccess } from "./api";
import { MachineAccessPanel } from "./MachineAccessPanel";

/** A member's own page, staff side: what machines they may use, with give and revoke. Hidden when the viewer has no machine authority. */
export function MemberMachineAccessSection({ makerspaceId, userId, name }: { makerspaceId: number; userId: number; name: string }) {
  const probe = useQuery({ queryKey: accessKeys.list(makerspaceId, { memberId: userId, status: "live", page: 1 }), queryFn: () => listAccess(makerspaceId, { memberId: userId, status: "live" }), retry: false });
  const machines = useQuery({ queryKey: ["machine-access", makerspaceId, "machines"], queryFn: () => getMachines(makerspaceId), enabled: probe.isSuccess });
  const status = probe.error instanceof StructuredApiError ? probe.error.status : undefined;
  if (status === 403 || status === 404 || probe.isError || !probe.isSuccess || !Array.isArray(probe.data?.results)) return null;
  const rows = machines.data?.results ?? [];
  const types = new Map(rows.map(row => [row.machine_type.id, row.machine_type.name]));
  return <section className="grid min-w-0 gap-3 border-t border-line pt-4" aria-label={t`Machine access`}>
    <MachineAccessPanel makerspaceId={makerspaceId} memberId={userId} preselected={[{ user_id: userId, name }]}
      targets={{ types: [...types].map(([id, label]) => ({ id, name: label })), machines: rows.map(row => ({ id: row.id, name: row.name, machine_type: row.machine_type.id })) }} />
  </section>;
}
