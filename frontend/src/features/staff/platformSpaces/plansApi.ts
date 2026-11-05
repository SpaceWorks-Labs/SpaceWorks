import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { publicV1Request, staffRequest } from "../../../lib/api";
import { healthKey, post, type Page } from "./spacesApi";

export type ManagedPlansConfig = { enabled: true; online_billing: boolean };

/** `managed_plans` is in `/config` only when the limiter is on; without it nothing of the limiter renders. */
export function useManagedPlans() {
  const config = useQuery({
    queryKey: ["public-config", "managed-plans"],
    queryFn: () => publicV1Request<{ managed_plans?: ManagedPlansConfig }>("/config"),
    staleTime: 5 * 60_000,
    retry: false,
  });
  return config.data?.managed_plans?.enabled === true ? config.data.managed_plans : null;
}

export const LIMIT_KEYS = ["members", "staff", "storage", "email_monthly", "sms_monthly", "whatsapp_monthly", "events_monthly",
  "products", "assets", "machines", "bookings", "api_clients"] as const;
export type LimitKey = typeof LIMIT_KEYS[number];
export const LIMIT_LABELS: Record<LimitKey, string> = {
  members: "Members", staff: "Staff", storage: "Storage (bytes)", email_monthly: "Emails per month", sms_monthly: "SMS per month",
  whatsapp_monthly: "WhatsApp per month", events_monthly: "Events per month", products: "Products", assets: "Assets",
  machines: "Machines", bookings: "Bookings", api_clients: "API clients",
};
export type HostingPlan = {
  id: number; key: string; name: string; description: string; is_active: boolean; trial_days: number;
  price_minor: number; currency: string; billing_period: "monthly" | "yearly" | "none";
  limits: Partial<Record<LimitKey, number | null>>; allowed_modules: string[]; space_count: number; created_at: string; updated_at: string;
};
export type PlanBody = Omit<HostingPlan, "id" | "space_count" | "created_at" | "updated_at">;
export type PlanAssignment = { makerspace_id: number; plan: HostingPlan; assigned_at: string; trial_ends_at: string | null; trial_expired: boolean };
export type InvoiceReceipt = { method: string; reference: string; received_on: string; amount_minor: number; recorded_at: string; recorded_by?: string | null; note: string };
export type HostingInvoice = {
  id: number; number: string; makerspace: { id: number; name: string } | null; makerspace_name: string; description: string;
  amount_minor: number; currency: string; due_on: string; period_start: string | null; period_end: string | null;
  status: "open" | "paid" | "void"; overdue: boolean; paid_at: string | null; voided_at: string | null; void_reason: string;
  receipts: InvoiceReceipt[]; online_payable: boolean; created_at: string;
};
export type BillingSettings = {
  auto_enforce_enabled: boolean; grace_days: number; online_billing_switch: boolean; provider: "" | "stripe" | "razorpay";
  stripe_secret_key_set: boolean; stripe_webhook_secret_set: boolean; razorpay_key_id: string;
  razorpay_key_secret_set: boolean; razorpay_webhook_secret_set: boolean; updated_at: string;
};

const P = "/admin/platform";
const plansKey = ["platform-hosting-plans"] as const;
const invoicesKey = ["platform-hosting-invoices"] as const;
const billingKey = ["platform-hosting-billing"] as const;

export function formatMoney(minor: number, currency: string) {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(minor / 100);
  } catch {
    return `${(minor / 100).toFixed(2)} ${currency}`;
  }
}

export function usePlans(enabled = true) {
  return useQuery({ queryKey: plansKey, queryFn: () => staffRequest<HostingPlan[] | Page<HostingPlan>>(`${P}/hosting-plans`, {}, "platform"),
    select: (data) => Array.isArray(data) ? data : data.results, enabled });
}

export function useSavePlan(id: number | null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PlanBody) => id === null ? post<HostingPlan>(`${P}/hosting-plans`, body)
      : staffRequest<HostingPlan>(`${P}/hosting-plans/${id}`, { method: "PATCH", body: JSON.stringify(body) }, "platform"),
    onSuccess: () => client.invalidateQueries({ queryKey: plansKey }),
  });
}

export function useSpacePlan(spaceId: number) {
  return useQuery({ queryKey: ["platform-space-plan", spaceId], queryFn: () => staffRequest<PlanAssignment | null>(`${P}/spaces/${spaceId}/plan`, {}, "platform") });
}

export function useAssignPlan(spaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { plan_id: number; trial_days: number | null } | null): Promise<PlanAssignment | null> => body
      ? staffRequest<PlanAssignment>(`${P}/spaces/${spaceId}/plan`, { method: "PUT", body: JSON.stringify(body) }, "platform")
      : staffRequest<void>(`${P}/spaces/${spaceId}/plan`, { method: "DELETE" }, "platform").then(() => null),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["platform-space-plan", spaceId] });
      void client.invalidateQueries({ queryKey: healthKey });
      void client.invalidateQueries({ queryKey: plansKey });
    },
  });
}

export function useInvoices(status: string, page: number) {
  return useQuery({ queryKey: [...invoicesKey, status, page],
    queryFn: () => staffRequest<Page<HostingInvoice>>(`${P}/hosting-invoices?${new URLSearchParams({ ...(status ? { status } : {}), page: String(page) })}`, {}, "platform") });
}

/** `path` is "" to create, or "<id>/record-payment" / "<id>/void". */
export function useInvoiceAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) => post<HostingInvoice>(`${P}/hosting-invoices${path ? `/${path}` : ""}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: invoicesKey }),
  });
}

export function useBillingSettings() {
  return useQuery({ queryKey: billingKey, queryFn: () => staffRequest<BillingSettings>(`${P}/hosting-billing-settings`, {}, "platform") });
}

export function useSaveBillingSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => staffRequest<BillingSettings>(`${P}/hosting-billing-settings`, { method: "PATCH", body: JSON.stringify(body) }, "platform"),
    onSuccess: (data) => client.setQueryData(billingKey, data),
  });
}
