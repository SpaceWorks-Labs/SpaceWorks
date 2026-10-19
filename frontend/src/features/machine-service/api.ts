import { memberRequest, publicV1Request } from "../../lib/api";
import type { MachineServiceStatus, OwnerControls } from "./types";

/** Anonymous bearer-token status read (any machine type). Never authorizes a write. */
export function fetchServiceStatus(publicToken: string) {
  return publicV1Request<MachineServiceStatus>(`/public/machine-service/requests/${encodeURIComponent(publicToken)}/status`);
}

/** Owner-only: resolves a tracking token to the caller's own job id and cancel eligibility. */
export function fetchOwnerControls(publicToken: string) {
  return memberRequest<OwnerControls>(`/member/machine-service/requests/by-token/${encodeURIComponent(publicToken)}/owner`);
}

/** Owner-only cancellation on the member surface; staff use the admin action route. */
export function cancelOwnServiceRequest(requestId: number, reason = "") {
  return memberRequest<MachineServiceStatus>(`/member/machine-service/requests/${requestId}/cancel`, {
    method: "POST",
    body: JSON.stringify(reason ? { reason } : {}),
  });
}

export const serviceKeys = {
  status: (token: string) => ["public-machine-service-status", token] as const,
  owner: (token: string) => ["machine-service-owner", token] as const,
};
