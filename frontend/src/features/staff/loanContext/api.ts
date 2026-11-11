import { t } from "@lingui/core/macro";
import { staffRequest } from "../../../lib/api";

export type Domain = "event" | "booking";
export type Context = { active: boolean; generation: string; revision: number; can_write: boolean;
  event_id?: number; booking_id?: number; may_view_participant?: boolean; participant_registration_id?: number | null };
const safe = (v: unknown, min: number): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= min;
export function parseContext(value: unknown, domain: Domain): Context {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(t`Invalid context response`);
  const r = value as Record<string, unknown>;
  if (typeof r.active !== "boolean" || typeof r.can_write !== "boolean" || !safe(r.revision, 0)
    || typeof r.generation !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(r.generation)) throw new Error(t`Invalid context response`);
  const key = domain === "event" ? "event_id" : "booking_id";
  if (r.active && !safe(r[key], 1)) throw new Error(t`Invalid context target`);
  if (!r.active && (r.event_id != null || r.booking_id != null || r.participant_registration_id != null)) throw new Error(t`Invalid inactive context`);
  if (domain === "event" && r.active) {
    if (typeof r.may_view_participant !== "boolean") throw new Error(t`Invalid participant visibility`);
    // First-slice event writes always require participant-management authority.
    if (r.can_write && !r.may_view_participant) throw new Error(t`Invalid event write authority`);
    if (r.may_view_participant && !(r.participant_registration_id === null || safe(r.participant_registration_id, 1))) throw new Error(t`Invalid participant`);
    if (!r.may_view_participant && "participant_registration_id" in r) throw new Error(t`Unexpected participant disclosure`);
  }
  return r as Context;
}
export function contextPath(tenant: number, request: number, domain: Domain, intended?: number) {
  const base = `/admin/makerspace/${tenant}/requests/${request}/${domain}-context`;
  return intended ? `${base}?intended_${domain}_id=${intended}` : base;
}
export async function getContext(tenant: number, request: number, domain: Domain, intended?: number) {
  return parseContext(await staffRequest<unknown>(contextPath(tenant, request, domain, intended)), domain);
}
export async function putContext(tenant: number, request: number, domain: Domain, target: number, participant: number | null, state: Context) {
  const body = domain === "event" ? { event_id: target, participant_registration_id: participant } : { booking_id: target };
  return parseContext(await staffRequest<unknown>(contextPath(tenant, request, domain), { method: "PUT", body: JSON.stringify({ ...body, expected_generation: state.generation, expected_revision: state.revision }) }), domain);
}
export async function deleteContext(tenant: number, request: number, domain: Domain, target: number, state: Context) {
  return parseContext(await staffRequest<unknown>(contextPath(tenant, request, domain, target), { method: "DELETE", body: JSON.stringify({ expected_generation: state.generation, expected_revision: state.revision }) }), domain);
}
