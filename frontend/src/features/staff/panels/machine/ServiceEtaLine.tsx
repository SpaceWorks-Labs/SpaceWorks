import type { MachineServiceRequest } from "../../../../generated/api";
import { ServiceRequestEta } from "../../../machine-service/ServiceRequestEta";

/** Server ETA in a staff queue row; terminal rows (null ETA) render nothing. */
export function ServiceEtaLine({ request }: { request: MachineServiceRequest }) {
  if (!request.eta) return null;
  return <span className="mt-1 block"><ServiceRequestEta eta={request.eta} status={request.status} compact /></span>;
}

/** Shown in the staff cancel confirmation: what cancelling does to stock, money and the requester. */
export function CancelNotice() {
  return <p className="text-sm text-muted sm:col-span-2">
    Cancelling returns any reserved material to its pool, charges nothing, frees the machine if the job is running,
    and tells the requester. Jobs behind it move up. For a running job, the material used so far stays taken from
    stock and is costed, never charged.
  </p>;
}
