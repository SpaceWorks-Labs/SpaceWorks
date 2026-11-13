import { t } from "@lingui/core/macro";
import { useMemo } from "react";

import { DetailLayout } from "../../components/layouts";
import type { Machine } from "../staff/machinesApi";
import { MachineAccessPanel } from "./MachineAccessPanel";

/** Machines > Machine access: every grant in the space (or in the viewer's machine scope), grant and revoke. */
export function MachineAccessScreen({ makerspaceId, machines, onBack }: { makerspaceId: number; machines: Machine[]; onBack: () => void }) {
  const targets = useMemo(() => {
    const types = new Map<number, string>();
    machines.forEach(machine => types.set(machine.machine_type.id, machine.machine_type.name));
    return { types: [...types].map(([id, name]) => ({ id, name })),
      machines: machines.map(machine => ({ id: machine.id, name: machine.name, machine_type: machine.machine_type.id })) };
  }, [machines]);
  return <DetailLayout title={t`Machine access`} back={{ label: t`Machines`, onClick: onBack }}
    meta={[t`Who may use which machine, given by a space manager`]} state={{ status: "ready" }}
    main={<MachineAccessPanel makerspaceId={makerspaceId} targets={targets} />} />;
}
