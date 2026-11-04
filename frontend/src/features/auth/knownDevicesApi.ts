/**
 * STUB(S-B): `GET auth/devices` and `DELETE auth/devices/<id>` from S-B's brief. They are not in
 * `generated/api.ts` yet, so this one shape is hand-typed from S0's `KnownDevice` model
 * (`ua_label`, `last_verified_at`); swap it for the generated type when the coordinator
 * regenerates the client at the S-B merge. A list or a paginated page are both accepted.
 */
import { staffRequest } from "../../lib/api";

export type KnownDevice = {
  id: number;
  ua_label: string | null;
  last_verified_at: string;
  /** True for the browser making the request, when the server can tell. */
  current?: boolean;
};

type DevicesResponse = KnownDevice[] | { results?: KnownDevice[]; devices?: KnownDevice[] };

export async function listKnownDevices(): Promise<KnownDevice[]> {
  const data = await staffRequest<DevicesResponse>("/auth/devices");
  return Array.isArray(data) ? data : data.results ?? data.devices ?? [];
}

export const forgetKnownDevice = (id: number) => staffRequest<void>(`/auth/devices/${id}`, { method: "DELETE" });
