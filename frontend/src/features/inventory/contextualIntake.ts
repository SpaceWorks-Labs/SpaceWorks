import { t } from "@lingui/core/macro";
import { memberRequest, staffRequest } from "../../lib/api";

type Items = { product_id: number; quantity: number }[];
type Selection = { items: Items; kit?: never } | { items?: never; kit: { id: number; version: number } };
export type RequestFields = Selection & { requested_for: string; website?: string; pickup_from?: string; pickup_until?: string; waitlist_entry_id?: number };
export type SelfBody = RequestFields & { operation_id: string; event_registration_id: number | null; booking_token: string | null };
export type StaffBody = RequestFields & { operation_id: string; borrower_id?: number; event_registration_id: number | null; booking_id: number | null };
export type SelfResult = { kind: "request"; public_token: string; status: string; replayed: boolean } | { kind: "consumable_plan"; plan_id: number; replayed: boolean };
export type StaffResult = { kind: "request"; request_id: number; status: string; replayed: boolean } | { kind: "consumable_plan"; plan_id: number; replayed: boolean };

/** One scope owns one frozen intent. A transport failure never creates a replacement UUID. */
export class PendingIntake<T> {
  private body: string | undefined;
  private scope: string | undefined;
  private inFlight = false;
  private uncertain = false;
  private listeners = new Set<() => void>();
  subscribe(listener: () => void): () => void { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  private notify(): void { for (const listener of this.listeners) listener(); }
  begin(scope: string, body: T): Readonly<T> {
    if (this.body) throw new Error(t`Review the existing request before starting another.`);
    this.scope = scope;
    this.body = JSON.stringify(body);
    this.notify();
    return JSON.parse(this.body) as T;
  }
  current(scope: string): Readonly<T> | undefined {
    if (this.scope !== scope) return undefined;
    return this.body === undefined ? undefined : JSON.parse(this.body) as T;
  }
  has(scope: string): boolean { return this.scope === scope && this.body !== undefined; }
  wasUncertain(scope: string): boolean { return this.has(scope) && this.uncertain; }
  state(scope: string): "idle" | "sending" | "uncertain" {
    return !this.has(scope) ? "idle" : this.inFlight ? "sending" : "uncertain";
  }
  acquire(scope: string, body: Readonly<T>): boolean {
    if (this.inFlight || this.scope !== scope || this.body !== JSON.stringify(body)) return false;
    this.inFlight = true; this.notify(); return true;
  }
  release(scope: string, body: Readonly<T>): void {
    if (this.inFlight && this.scope === scope && this.body === JSON.stringify(body)) { this.inFlight = false; this.uncertain = true; this.notify(); }
  }
  complete(scope: string, body: Readonly<T>): boolean {
    if (this.scope !== scope || this.body === undefined || this.body !== JSON.stringify(body)) return false;
    this.clear(); return true;
  }
  retire(scope: string): void { if (this.scope === scope) this.clear(); }
  /** Drop a request retained for any other actor scope, so it can never be replayed by this one. */
  retainOnly(scope: string): void { if (this.body !== undefined && this.scope !== scope) this.clear(); }
  clear(): void { const changed = this.body !== undefined; this.body = undefined; this.scope = undefined; this.inFlight = false; this.uncertain = false; if (changed) this.notify(); }
}

function result(value: unknown, staff: boolean): SelfResult | StaffResult {
  if (!value || typeof value !== "object") throw new Error(t`Invalid request response.`);
  const row = value as Record<string, unknown>;
  if (typeof row.replayed !== "boolean") throw new Error(t`Invalid request response.`);
  if (row.kind === "consumable_plan" && typeof row.plan_id === "number" && Number.isSafeInteger(row.plan_id) && row.plan_id > 0)
    return { kind: "consumable_plan", plan_id: row.plan_id, replayed: row.replayed };
  if (row.kind === "request" && typeof row.status === "string") {
    if (staff && typeof row.request_id === "number" && Number.isSafeInteger(row.request_id) && row.request_id > 0)
      return { kind: "request", request_id: row.request_id, status: row.status, replayed: row.replayed };
    if (!staff && typeof row.public_token === "string" && row.public_token.length > 0)
      return { kind: "request", public_token: row.public_token, status: row.status, replayed: row.replayed };
  }
  throw new Error(t`Invalid request response.`);
}

export async function submitContextualSelf(slug: string, body: Readonly<SelfBody>): Promise<SelfResult> {
  const value = await memberRequest<unknown>(`/public/${encodeURIComponent(slug)}/requests/contextual`, { method: "POST", body: JSON.stringify(body) });
  const parsed = result(value, false);
  if (parsed.kind === "request" && !("public_token" in parsed)) throw new Error(t`Invalid request response.`);
  return parsed;
}
export async function submitContextualStaff(makerspaceId: number, body: Readonly<StaffBody>): Promise<StaffResult> {
  if (!Number.isSafeInteger(makerspaceId) || makerspaceId < 1 || (!body.event_registration_id && !body.booking_id)) throw new Error(t`Choose an authorized event or booking.`);
  const value = await staffRequest<unknown>(`/admin/makerspace/${makerspaceId}/equipment-requests/contextual`, { method: "POST", body: JSON.stringify(body) });
  const parsed = result(value, true);
  if (parsed.kind === "request" && !("request_id" in parsed)) throw new Error(t`Invalid request response.`);
  return parsed;
}
