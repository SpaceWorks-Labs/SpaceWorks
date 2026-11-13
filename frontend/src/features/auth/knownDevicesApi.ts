/** `GET auth/devices` and `DELETE auth/devices/<id>` (S-B), typed from the generated client. */
import type { KnownDevice, KnownDeviceList } from "../../generated/api";
import { staffRequest } from "../../lib/api";

export type { KnownDevice };
/** `remembered_days`: how long a device stays remembered without a sign-in (strictest across staff spaces). */
export type KnownDevices = KnownDeviceList;

export const listKnownDevices = () => staffRequest<KnownDevices>("/auth/devices");

export const forgetKnownDevice = (id: number) => staffRequest<void>(`/auth/devices/${id}`, { method: "DELETE" });
