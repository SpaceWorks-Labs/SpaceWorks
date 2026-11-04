/**
 * STUB(S-B): `GET auth/devices` and `DELETE auth/devices/<id>`. Hand-typed from S-B's
 * `KnownDeviceListSerializer` on lane/r2-s-b (efae28ce) because they are not in
 * `generated/api.ts` yet; swap both types for the generated ones when the coordinator
 * regenerates the client at the S-B merge.
 */
import { staffRequest } from "../../lib/api";

export type KnownDevice = {
  id: number;
  /** A coarse label such as "Firefox on Windows". */
  label: string;
  created_at: string;
  /** The last completed sign-in on this device. */
  last_verified_at: string;
  /** This browser or app. */
  current: boolean;
};

export type KnownDevices = {
  devices: KnownDevice[];
  /** How long a device stays remembered without a sign-in (strictest across the person's staff spaces). */
  remembered_days: number;
};

export const listKnownDevices = () => staffRequest<KnownDevices>("/auth/devices");

export const forgetKnownDevice = (id: number) => staffRequest<void>(`/auth/devices/${id}`, { method: "DELETE" });
