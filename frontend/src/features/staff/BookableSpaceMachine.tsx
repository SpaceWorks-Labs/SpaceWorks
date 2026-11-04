import { useQuery } from "@tanstack/react-query";

import { capabilityOn } from "../../lib/features";
import { staffRequest } from "../../lib/api";
import { getMachines, machineKeys } from "./machinesApi";

type SpaceFlags = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/**
 * Is `machines.time_booking` on? Read from the staff session's cached makerspace list (never fetched
 * here, like `useStaffPricingOn`). `undefined` means this form cannot tell; the server refuses the
 * "machine" kind itself when the switch is off.
 */
export function useMachineTimeBookingOn(makerspaceId: number): boolean | undefined {
  const spaces = useQuery({ queryKey: ["staff", "makerspaces"], queryFn: () => staffRequest<SpaceFlags[]>("/admin/makerspaces"), enabled: false });
  const space = Array.isArray(spaces.data) ? spaces.data.find(row => row.id === makerspaceId) : undefined;
  return space ? capabilityOn(space, "machines.time_booking") : undefined;
}

/** The machine whose time this resource books. Choosing one also sets its machine type on the server. */
export function BookableSpaceMachine({ makerspaceId, id, value, onChange }: {
  makerspaceId: number; id: string; value: number | null; onChange: (value: number | null) => void;
}) {
  const query = useQuery({ queryKey: machineKeys.list(makerspaceId), queryFn: () => getMachines(makerspaceId), retry: false });
  const rows = (query.data?.results ?? []).filter(machine => machine.is_active);
  return <>
    <select id={id} className="desk-input w-full" required value={value ?? ""} onChange={event => onChange(event.target.value ? Number(event.target.value) : null)}>
      <option value="">Choose a machine</option>
      {value && !rows.some(machine => machine.id === value) ? <option value={value}>Linked machine #{value}</option> : null}
      {rows.map(machine => <option key={machine.id} value={machine.id}>{machine.name} · {machine.machine_type.name}</option>)}
    </select>
    {query.isLoading ? <p role="status" className="mt-2 text-sm text-muted">Loading machines…</p> : null}
    {query.isError ? <p className="mt-2 text-sm text-muted">Machines are unavailable: {query.error.message}</p> : null}
  </>;
}
