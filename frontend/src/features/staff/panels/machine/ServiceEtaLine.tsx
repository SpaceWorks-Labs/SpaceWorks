import type { MachineServiceRequest } from "../../../../generated/api";
import { ServiceRequestEta } from "../../../machine-service/ServiceRequestEta";
import type { WithEta } from "../../../machine-service/types";

/** Server ETA in a staff queue row; terminal rows (null ETA) render nothing. */
export function ServiceEtaLine({ request }: { request: MachineServiceRequest }) {
  const eta = (request as MachineServiceRequest & WithEta).eta;
  if (!eta) return null;
  return <span className="mt-1 block"><ServiceRequestEta eta={eta} status={request.status} compact /></span>;
}

/** Shown in the staff cancel confirmation: what cancelling does to stock, money and the requester. */
export function CancelNotice() {
  return <p className="text-sm text-muted sm:col-span-2">
    Cancelling returns any reserved material to its pool, charges nothing, frees the machine if the job is running,
    and tells the requester. Jobs behind it move up.
  </p>;
}
