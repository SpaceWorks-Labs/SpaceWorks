import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field, PagePager } from "../../components/ui";
import { useMemberMachines } from "./api";

function statusNote(status: string) {
  switch (status) {
    case "running": return ` · ${t`in use`}`;
    case "reserved": return ` · ${t`reserved`}`;
    case "maintenance": return ` · ${t`under maintenance`}`;
    case "offline": return ` · ${t`offline`}`;
    default: return "";
  }
}

/** The machine for a new supervised session, chosen from the member's machine list (with ids).
 *  Anyone the list refuses (no active membership here, machines off) types the machine number. */
export function SupervisedMachineSelect({ makerspaceId, value, onChange }: {
  makerspaceId: number; value: string; onChange: (value: string) => void;
}) {
  const [page, setPage] = useState(1);
  const machines = useMemberMachines(makerspaceId, page);
  const digits = (text: string) => text.replace(/\D/g, "");
  if (machines.isError) return <Field label={t`Machine number`} hint={t`The number in the machine's QR link.`}>
    <input className="desk-input" inputMode="numeric" pattern="[0-9]*" value={value} onChange={change => onChange(digits(change.target.value))} />
  </Field>;
  const rows = machines.data?.results ?? [];
  return <div className="grid gap-2">
    <Field label={t`Machine`} hint={rows.length || machines.isPending ? undefined : t`No machines are listed for members here.`}>
      <select className="desk-input" value={value} disabled={machines.isPending} onChange={change => onChange(change.target.value)}>
        <option value="">{machines.isPending ? t`Loading machines…` : t`Select a machine`}</option>
        {rows.map(row => <option key={row.id} value={String(row.id)}>
          {row.name} · {row.machine_type.name}{statusNote(row.status)}</option>)}
      </select>
    </Field>
    <PagePager page={page} setPage={setPage} next={machines.data?.next} />
  </div>;
}
