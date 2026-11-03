import { staffRequest } from "../../../lib/api";

/** One row of the merged consumables list (MI-40): an item, a per-machine consumable or a material pool. */
export type ConsumableRow = {
  source: "item" | "machine" | "pool";
  id: number;
  name: string;
  machine_id: number | null;
  machine_name: string;
  unit: string;
  remaining: string;
  threshold: string | null;
  status: "ok" | "low";
  open_to_buy_id: number | null;
};

export type ConsumablePage = { count: number; next: string | null; previous: string | null; results: ConsumableRow[] };
export type ConsumableStatus = "all" | "low" | "ok";

export const CONSUMABLES_PAGE_SIZE = 24;

export const consumableKeys = {
  all: (makerspaceId: number) => ["consumables", makerspaceId] as const,
  list: (makerspaceId: number, status: ConsumableStatus, page: number) => ["consumables", makerspaceId, status, page] as const,
};

export function consumablesPath(makerspaceId: number, status: ConsumableStatus, page: number) {
  const params = new URLSearchParams();
  if (status !== "all") params.set("status", status);
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return `/admin/makerspace/${makerspaceId}/consumables${query ? `?${query}` : ""}`;
}

/** Take-and-go use of an item consumable: the server lowers stock through the availability module. */
export function logConsumableUse(makerspaceId: number, productId: number, quantity: number, note: string) {
  return staffRequest<ConsumableRow>(`/admin/makerspace/${makerspaceId}/consumables/${productId}/use`, {
    method: "POST", body: JSON.stringify({ quantity, note }),
  });
}

export const SOURCE_LABELS: Record<ConsumableRow["source"], string> = { item: "Item", machine: "Machine", pool: "Material pool" };
export const SOURCE_TONES = { item: "accent", machine: "info", pool: "neutral" } as const;

export function unitLabel(unit: string) {
  if (unit === "count") return "left";
  if (unit === "grams") return "g left";
  return `${unit} left`;
}
